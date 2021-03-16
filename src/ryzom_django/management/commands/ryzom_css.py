from django.core.management.base import BaseCommand, CommandError

from ryzom_django import bundle


class Command(BaseCommand):
    help = 'Output CSS bundle from Ryzom components'

    def handle(self, *args, **options):
        self.stdout.write(bundle.css())
