from django.conf import settings as django_settings

try:
    django_settings.configure()
except RuntimeError:
    pass

from django.core.cache import cache

from expiringdict import ExpiringDict

from setman.models import Settings
from setman.utils import AVAILABLE_SETTINGS, is_settings_container


__all__ = ('LazySettings', )


CACHE_KEY = 'setman__custom_cache'


class LazySettings(object):
    """
    Simple proxy object that accessed database only when user needs to read
    some setting.
    """

    def __init__(self, settings=None, prefix=None, parent=None):
        """
        Initialize lazy settings instance.
        """
        self._settings = settings or AVAILABLE_SETTINGS
        self._parent = parent
        self._prefix = prefix
        self._cache = ExpiringDict(max_len=20, max_age_seconds=10)

    def __delattr__(self, name):
        if name.startswith('_'):
            return self._safe_super_method('__delattr__', name)

        if hasattr(django_settings, name):
            delattr(django_settings, name)
        else:
            custom = self._custom
            delattr(custom, name)
            custom.save()
            cache.delete(CACHE_KEY)

    def _get_setting_value(self, name):
        data, prefix = self._custom.data, self._prefix

        # Read app setting from database
        if prefix and prefix in data and name in data[prefix]:
            return data[prefix][name]
        # Read project setting from database
        elif name in data and not isinstance(data[name], dict):
            return data[name]
        # Or from Django settings
        elif hasattr(django_settings, name):
            return getattr(django_settings, name)
        # Or read default value from available settings
        elif hasattr(self._settings, name):
            mixed = getattr(self._settings, name)

            if is_settings_container(mixed):
                return LazySettings(mixed, name, self)

            return mixed.default

        # If cannot read setting - raise error
        raise AttributeError('Settings has not attribute %r' % name)

    def __getattr__(self, name):
        """
        Add support for getting settings keys as instance attribute.

        For first try, method tries to read settings from database, then from
        Django settings and if all fails try to return default value of
        available setting from configuration definition file if any.
        """
        if name.startswith('_'):
            return self._safe_super_method('__getattr__', name)

        from_cache = self._cache.get(name, None)

        if from_cache is None:
            value = self._get_setting_value(name)
            self._cache[name] = value
            return value
        else:
            return from_cache

    def __setattr__(self, name, value):
        """
        Add support of setting values to settings as instance attribute.
        """
        if name.startswith('_'):
            return self._safe_super_method('__setattr__', name, value)

        # First of all try to setup value to Django setting
        if hasattr(django_settings, name):
            setattr(django_settings, name, value)
        # Then setup value to project setting
        elif not self._prefix:
            custom = self._custom
            setattr(custom, name, value)
            custom.save()
            cache.delete(CACHE_KEY)
        # And finally setup value to app setting
        else:
            custom = self._custom
            data, prefix = custom.data, self._prefix

            if not prefix in data:
                data[prefix] = {}

            data[prefix].update({name: value})
            custom.save()
            cache.delete(CACHE_KEY)

    def revert(self):
        """
        Revert settings to default values.
        """
        self._custom.revert()

    def save(self):
        """
        Save customized settings to the database.
        """
        self._custom.save()

    def _clear(self):
        """
        Clear custom settings cache.
        """
        if CACHE_KEY in cache:
            cache.delete(CACHE_KEY)

    #@threaded_cached_property_with_ttl(
    #    ttl=getattr(django_settings, 'SETMAN_PROPERTY_CACHE_TIMEOUT', 30))
    @property
    def _custom(self):
        """
        Read custom settings from database and store it to the instance cache.
        """
        if self._parent:
            return self._parent._custom

        from_cache = cache.get(CACHE_KEY)
        if not from_cache:
            custom = self._get_custom_settings()
            cache.set(CACHE_KEY, custom)
            return custom

        return from_cache

    def _get_custom_settings(self):
        """
        Do not read any settings before post_syncdb signal is called.
        """
        try:
            return Settings.objects.get()
        except Settings.DoesNotExist:
            return Settings.objects.create(data={})

    def _safe_super_method(self, method, *args, **kwargs):
        """
        Execute super ``method`` and format fancy error message on
        ``AttributeError``.
        """
        klass = self.__class__

        try:
            method = getattr(super(klass, self), method)
        except AttributeError:
            args = (
                klass.__name__,
                args[0] if method.endswith('attr__') else method
            )
            raise AttributeError('%r object has no attribute %r' % args)
        else:
            return method(*args, **kwargs)
