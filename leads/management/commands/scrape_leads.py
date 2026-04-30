"""
Management command to scrape sports companies and extract emails.
"""

import sys
from django.core.management.base import BaseCommand, CommandError
from leads.tasks import search_and_scrape_companies, bulk_scrape_from_queries
from leads.models import ScrapingTask


class Command(BaseCommand):
    help = 'Scrape sports companies and extract emails from websites'

    def add_arguments(self, parser):
        parser.add_argument(
            '--query', '-q',
            type=str,
            help='Search query (e.g., "football sports manufacturer")'
        )
        parser.add_argument(
            '--max-results', '-r',
            type=int,
            default=10,
            help='Maximum number of companies to scrape (default: 10)'
        )
        parser.add_argument(
            '--max-pages', '-p',
            type=int,
            default=5,
            help='Maximum pages to crawl per website (default: 5)'
        )
        parser.add_argument(
            '--async', '-a',
            action='store_true',
            help='Run asynchronously using Celery (default: synchronous)'
        )
        parser.add_argument(
            '--bulk', '-b',
            nargs='+',
            help='Multiple queries to scrape in bulk'
        )
        parser.add_argument(
            '--sport', '-s',
            type=str,
            help='Sport type for auto-generated query'
        )
        parser.add_argument(
            '--location', '-l',
            type=str,
            help='Location for auto-generated query'
        )
        parser.add_argument(
            '--wait',
            action='store_true',
            help='Wait for async task to complete and show results'
        )

    def handle(self, *args, **options):
        queries = []
        
        # Build queries
        if options['bulk']:
            queries = options['bulk']
        elif options['query']:
            queries = [options['query']]
        elif options['sport'] and options['location']:
            queries = [f"{options['sport']} sports manufacturer {options['location']}"]
        elif options['sport']:
            queries = [f"{options['sport']} sports manufacturer"]
        else:
            raise CommandError(
                'Please provide --query, --bulk, or both --sport and --location'
            )
        
        max_results = options['max_results']
        max_pages = options['max_pages']
        use_async = options['async']
        wait = options['wait']
        
        self.stdout.write(self.style.HTTP_INFO(
            f'Starting scrape for {len(queries)} query(s)...'
        ))
        self.stdout.write(f'  Max results per query: {max_results}')
        self.stdout.write(f'  Max pages per site: {max_pages}')
        self.stdout.write(f'  Mode: {"async" if use_async else "synchronous"}')
        
        if len(queries) > 1:
            # Bulk scraping
            self._handle_bulk(queries, max_results, max_pages, use_async, wait)
        else:
            # Single query
            self._handle_single(queries[0], max_results, max_pages, use_async, wait)
    
    def _handle_single(self, query, max_results, max_pages, use_async, wait):
        """Handle single query scraping"""
        # Create tracking task
        task_obj = ScrapingTask.objects.create(
            query=query,
            status='pending',
        )
        
        self.stdout.write(f'\nQuery: {query}')
        self.stdout.write(f'Task ID: {task_obj.id}')
        
        if use_async:
            # Queue async task
            result = search_and_scrape_companies.delay(
                query=query,
                max_results=max_results,
                max_pages_per_site=max_pages,
                task_id=str(task_obj.id),
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Queued async task: {result.id}'
            ))
            
            if wait:
                self.stdout.write('Waiting for task to complete...')
                try:
                    task_result = result.get(timeout=300)
                    self._print_results(task_result)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error: {e}'))
        else:
            # Execute synchronously
            try:
                result = search_and_scrape_companies(
                    query=query,
                    max_results=max_results,
                    max_pages_per_site=max_pages,
                    task_id=str(task_obj.id),
                )
                self._print_results(result)
            except Exception as e:
                task_obj.status = 'failed'
                task_obj.errors = str(e)
                task_obj.save()
                raise CommandError(f'Scraping failed: {e}')
    
    def _handle_bulk(self, queries, max_results, max_pages, use_async, wait):
        """Handle bulk query scraping"""
        self.stdout.write(f'\nBulk queries: {queries}')
        
        if use_async:
            result = bulk_scrape_from_queries.delay(
                queries=queries,
                max_results_per_query=max_results,
                max_pages_per_site=max_pages,
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Queued bulk async task: {result.id}'
            ))
            
            if wait:
                self.stdout.write('Waiting for bulk task to complete...')
                try:
                    task_result = result.get(timeout=600)
                    self._print_bulk_results(task_result)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error: {e}'))
        else:
            # Execute synchronously
            try:
                result = bulk_scrape_from_queries(
                    queries=queries,
                    max_results_per_query=max_results,
                    max_pages_per_site=max_pages,
                )
                self._print_bulk_results(result)
            except Exception as e:
                raise CommandError(f'Bulk scraping failed: {e}')
    
    def _print_results(self, result):
        """Print single query results"""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Scraping completed!'))
        self.stdout.write('=' * 50)
        self.stdout.write(f"Query: {result.get('query', 'N/A')}")
        self.stdout.write(f"Total found: {result.get('total_found', 0)}")
        self.stdout.write(f"Total saved: {result.get('total_saved', 0)}")
        self.stdout.write(f"Duplicates skipped: {result.get('duplicates_skipped', 0)}")
        self.stdout.write(f"No emails: {result.get('no_emails', 0)}")
        self.stdout.write(f"Errors: {result.get('errors', 0)}")
    
    def _print_bulk_results(self, result):
        """Print bulk results"""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('Bulk scraping completed!'))
        self.stdout.write('=' * 50)
        self.stdout.write(f"Queries processed: {result.get('queries_processed', 0)}")
        self.stdout.write(f"Total found: {result.get('total_found', 0)}")
        self.stdout.write(f"Total saved: {result.get('total_saved', 0)}")
        self.stdout.write(f"Duplicates: {result.get('duplicates', 0)}")
        self.stdout.write(f"Failed: {result.get('failed', 0)}")
