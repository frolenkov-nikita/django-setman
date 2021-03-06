from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from setman.fields import SettingsField
from setman.managers import CACHE_KEY, SettingsManager
from setman.utils import AVAILABLE_SETTINGS, is_settings_container


__all__ = ('Settings', )


class Settings(models.Model):
    """
    Store all custom project settings in ``data`` field as ``json`` dump.

    Model also have two more fields:

    * ``create_date`` - Time when model instance has been created.
    * ``update_date`` - Time when model instance has been changed last time.

    """
    data = SettingsField(_('data'), blank=True, default='', editable=False)

    create_date = models.DateTimeField(_('created at'), auto_now_add=True)
    update_date = models.DateTimeField(_('updated at'), auto_now=True)

    objects = SettingsManager()

    class Meta:
        verbose_name = _('settings')
        verbose_name_plural = _('settings')

    def __delattr__(self, name):
        if not self.is_setting_name(name):
            return super(Settings, self).__delattr__(name)

        if name in self.data:
            del self.data[name]

    def __getattr__(self, name):
        if not self.is_setting_name(name):
            return super(Settings, self).__getattr__(name)

        return self.data.get(name)

    def __setattr__(self, name, value):
        if not self.is_setting_name(name):
            return super(Settings, self).__setattr__(name, value)

        if not self.data:
            self.data = {}
        self.data[name] = value

    def __unicode__(self):
        return 'Project settings'

    def is_setting_name(self, name):
        """
        Is name a valid setting name or not?
        """
        possible_names = ('create_date', 'data', 'id', 'objects', 'pk',
                          'update_date')
        return not name.startswith('_') and not name in possible_names

    def revert(self, app_name=None):
        """
        Revert all stored settings to default values.
        """
        data = self.data.get(app_name, {}) if app_name else self.data
        values = getattr(AVAILABLE_SETTINGS, app_name) if app_name \
                                                       else AVAILABLE_SETTINGS

        for name, value in data.items():
            mixed = getattr(values, name, None)

            # Pass if ``name`` isn't on available settings values
            if mixed is None:
                continue

            if is_settings_container(mixed):
                self.revert(name)
            else:
                data[name] = mixed.default

    def validate_unique(self, exclude=None):
        """
        Check that no else ``Settings`` insances has been created.
        """
        lookup = {} if not self.pk else {'pk': self.pk}
        counter = self._default_manager.exclude(**lookup).count()

        if counter != 0:
            raise ValidationError('Only one Settings instance could be ' \
                                  'created.')

        return super(Settings, self).validate_unique(exclude)


@receiver(signals.post_save, sender=Settings)
def clear_settings_cache(instance, **kwargs):
    """
    Clear settings cache if any.
    """
    from setman import settings
    settings._clear()

    if CACHE_KEY in cache:
        cache.delete(CACHE_KEY)


@receiver(signals.pre_save, sender=Settings)
def validate_settings(instance, **kwargs):
    """
    Validate settings data before save to database.
    """
    try:
        instance.full_clean()
    except ValidationError, error:
        # Dirty hack to ignore error messages raised by Django when trying to
        # re-save already existed instance (it's okay cause we didn't operate
        # with instance directly read from database, we got instance field data
        # from the cache)
        if hasattr(error, 'message_dict') and \
           error.message_dict.keys() == ['id']:
            return
        raise
