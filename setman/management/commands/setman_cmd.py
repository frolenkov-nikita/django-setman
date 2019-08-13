import logging
from optparse import make_option
from django.core.management.base import BaseCommand

from setman.models import Settings
from setman.utils import AVAILABLE_SETTINGS, is_settings_container


DEFAULT_ACTION = 'check_setman'
logger = logging.getLogger('setman')


class Command(BaseCommand):
    """
    """
    help_text = 'Check setman configuration or create Settings instance with '\
                'default values.'

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('-d',
                            '--default-values',
                            action='store_true',
                            default=False,
                            dest='default_values',
                            help='Store default values to Settings model.')

        # Named (optional) arguments
        parser.add_argument('--delete',
                            action='store_true',
                            dest='delete',
                            default=False,
                            help='Delete poll instead of closing it')

    def check_setman(self, verbosity):
        """
        Check setman configuration.
        """
        if verbosity:
            print('Project settings:', file=self.stdout)
            print('Configuration definition file placed at ' \
                                  '%r\n' % AVAILABLE_SETTINGS.path, file=self.stdout)

            for setting in AVAILABLE_SETTINGS:
                indent = ' ' * 4

                if is_settings_container(setting):
                    print('%s%r settings:' % \
                                          (indent, setting.app_name), file=self.stdout)
                    print('%sConfiguration definition file ' \
                                          'placed at %r' % \
                                          (indent, setting.path), file=self.stdout)
                    indent *= 2

                    for subsetting in setting:
                        print('%s%r' % (indent, subsetting), file=self.stdout)

                    print(file=self.stdout)
                else:
                    print('%s%r' % (indent, setting), file=self.stdout)

            print('', file=self.stdout)

    def handle(self, **options):
        """
        Do all necessary things.
        """
        default_values = options.get('default_values', False)
        verbosity = int(options.get('verbosity', 1))

        self.check_setman(verbosity)

        if default_values:
            self.store_default_values(verbosity)

    def store_default_values(self, verbosity):
        """
        Store default values to Settings instance.
        """
        def store_values(settings, available_settings=None, prefix=None):
            available_settings = available_settings or AVAILABLE_SETTINGS

            for setting in available_settings:
                if is_settings_container(setting):
                    store_values(settings, setting, setting.app_name)
                elif not prefix:
                    setattr(settings, setting.name, setting.default)
                else:
                    data = settings.data

                    if not prefix in data:
                        data[prefix] = {}

                    data[prefix][setting.name] = setting.default

        try:
            settings = Settings.objects.get()
        except Settings.DoesNotExist:
            settings = Settings()
            if verbosity:
                print('Will create new Settings instance.', file=self.stdout)
        else:
            if verbosity:
                print('Settings instance already exist.', file=self.stdout)

        store_values(settings)
        settings.save()

        if verbosity:
            print('Default values stored well!', file=self.stdout)
