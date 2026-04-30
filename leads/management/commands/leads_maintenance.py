"""
Management command for lead maintenance operations.
"""

from django.core.management.base import BaseCommand, CommandError
from leads.tasks import validate_all_emails, export_leads_to_csv, cleanup_old_tasks
from leads.models import Lead, ScrapingTask


class Command(BaseCommand):
    help = 'Lead maintenance operations: validate, export, cleanup'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='operation', help='Operation to perform')
        
        # Validate operation
        validate_parser = subparsers.add_parser('validate', help='Validate all emails')
        validate_parser.add_argument(
            '--async', '-a',
            action='store_true',
            help='Run validation asynchronously'
        )
        
        # Export operation
        export_parser = subparsers.add_parser('export', help='Export leads to CSV')
        export_parser.add_argument(
            '--status', '-s',
            type=str,
            choices=['new', 'contacted', 'responded', 'converted', 'invalid'],
            help='Filter by status'
        )
        export_parser.add_argument(
            '--validated', '-v',
            action='store_true',
            help='Only export validated emails'
        )
        export_parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output file path (default: auto-generated in media/exports/)'
        )
        export_parser.add_argument(
            '--async', '-a',
            action='store_true',
            help='Run export asynchronously'
        )
        
        # Cleanup operation
        cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old tasks')
        cleanup_parser.add_argument(
            '--days', '-d',
            type=int,
            default=30,
            help='Delete tasks older than this many days (default: 30)'
        )
        cleanup_parser.add_argument(
            '--dry-run', '-n',
            action='store_true',
            help='Show what would be deleted without deleting'
        )
        
        # Stats operation
        stats_parser = subparsers.add_parser('stats', help='Show lead statistics')
    
    def handle(self, *args, **options):
        operation = options['operation']
        
        if operation == 'validate':
            self._handle_validate(options)
        elif operation == 'export':
            self._handle_export(options)
        elif operation == 'cleanup':
            self._handle_cleanup(options)
        elif operation == 'stats':
            self._handle_stats()
        else:
            self.stdout.write(self.style.ERROR('Please specify an operation: validate, export, cleanup, stats'))
    
    def _handle_validate(self, options):
        """Handle email validation"""
        self.stdout.write('Starting email validation...')
        
        if options['async']:
            result = validate_all_emails.delay()
            self.stdout.write(self.style.SUCCESS(f'Queued async task: {result.id}'))
        else:
            # Get count before
            total = Lead.objects.filter(email__isnull=False).exclude(email='').count()
            self.stdout.write(f'Validating {total} emails...')
            
            result = validate_all_emails()
            
            self.stdout.write(self.style.SUCCESS('Validation completed!'))
            self.stdout.write(f"  Total checked: {result.get('total', 0)}")
            self.stdout.write(f"  Valid: {result.get('valid', 0)}")
            self.stdout.write(f"  Invalid: {result.get('invalid', 0)}")
            self.stdout.write(f"  Normalized: {result.get('normalized', 0)}")
    
    def _handle_export(self, options):
        """Handle lead export"""
        self.stdout.write('Starting lead export...')
        
        kwargs = {}
        if options['status']:
            kwargs['status'] = options['status']
        if options['validated']:
            kwargs['email_validated'] = True
        
        if options['async']:
            result = export_leads_to_csv.delay(**kwargs)
            self.stdout.write(self.style.SUCCESS(f'Queued async export task: {result.id}'))
        else:
            filepath = export_leads_to_csv(**kwargs)
            self.stdout.write(self.style.SUCCESS(f'Export completed: {filepath}'))
    
    def _handle_cleanup(self, options):
        """Handle task cleanup"""
        days = options['days']
        dry_run = options['dry_run']
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_tasks = ScrapingTask.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        count = old_tasks.count()
        
        if dry_run:
            self.stdout.write(f'Would delete {count} tasks older than {days} days')
            for task in old_tasks[:10]:
                self.stdout.write(f'  - {task.id}: {task.query} ({task.created_at})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            if count == 0:
                self.stdout.write('No old tasks to delete')
                return
            
            self.stdout.write(f'Deleting {count} tasks older than {days} days...')
            old_tasks.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} tasks'))
    
    def _handle_stats(self):
        """Handle stats display"""
        from django.db.models import Count, Q
        
        total = Lead.objects.count()
        with_email = Lead.objects.exclude(email__isnull=True).exclude(email='').count()
        validated = Lead.objects.filter(email_validated=True).count()
        verified = Lead.objects.filter(email_verified=True).count()
        
        by_status = Lead.objects.values('status').annotate(count=Count('id'))
        by_source = Lead.objects.values('source').annotate(count=Count('id'))
        by_country = Lead.objects.exclude(country='').values('country').annotate(count=Count('id')).order_by('-count')[:10]
        
        pending_tasks = ScrapingTask.objects.filter(status='pending').count()
        in_progress_tasks = ScrapingTask.objects.filter(status='in_progress').count()
        completed_tasks = ScrapingTask.objects.filter(status='completed').count()
        failed_tasks = ScrapingTask.objects.filter(status='failed').count()
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.HTTP_INFO('LEAD STATISTICS'))
        self.stdout.write('=' * 50)
        
        self.stdout.write(f'\nTotal Leads: {total}')
        self.stdout.write(f'  With Email: {with_email} ({with_email/total*100:.1f}%)' if total else '  With Email: 0')
        self.stdout.write(f'  Without Email: {total - with_email}')
        self.stdout.write(f'  Email Validated: {validated}')
        self.stdout.write(f'  Email Verified: {verified}')
        
        self.stdout.write('\nBy Status:')
        for item in by_status:
            self.stdout.write(f'  {item["status"]}: {item["count"]}')
        
        self.stdout.write('\nBy Source:')
        for item in by_source:
            self.stdout.write(f'  {item["source"]}: {item["count"]}')
        
        self.stdout.write('\nTop Countries:')
        for item in by_country:
            self.stdout.write(f'  {item["country"]}: {item["count"]}')
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.HTTP_INFO('SCRAPING TASKS'))
        self.stdout.write('=' * 50)
        self.stdout.write(f'  Pending: {pending_tasks}')
        self.stdout.write(f'  In Progress: {in_progress_tasks}')
        self.stdout.write(f'  Completed: {completed_tasks}')
        self.stdout.write(f'  Failed: {failed_tasks}')
        self.stdout.write('')
