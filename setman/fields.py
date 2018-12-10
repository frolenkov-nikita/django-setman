from django.conf import settings as django_settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

import json as simplejson

from setman.utils import AVAILABLE_SETTINGS, is_settings_container


__all__ = ('SettingsField', )



class SubfieldBase(type):
    """
    A metaclass for custom Field subclasses. This ensures the model's attribute
    has the descriptor protocol attached to it.
    """
    def __new__(cls, name, bases, attrs):
        new_class = super(SubfieldBase, cls).__new__(cls, name, bases, attrs)
        new_class.contribute_to_class = make_contrib(
            new_class, attrs.get('contribute_to_class')
        )
        return new_class


class Creator(object):
    """
    A placeholder class that provides a way to set the attribute on the model.
    """
    def __init__(self, field):
        self.field = field

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return obj.__dict__[self.field.name]

    def __set__(self, obj, value):
        obj.__dict__[self.field.name] = self.field.to_python(value)


def make_contrib(superclass, func=None):
    """
    Returns a suitable contribute_to_class() method for the Field subclass.
    If 'func' is passed in, it is the existing contribute_to_class() method on
    the subclass and it is called before anything else. It is assumed in this
    case that the existing contribute_to_class() calls all the necessary
    superclass methods.
    """
    def contribute_to_class(self, cls, name, **kwargs):
        if func:
            func(self, cls, name, **kwargs)
        else:
            super(superclass, self).contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.name, Creator(self))

    return contribute_to_class


class SettingsField(models.TextField):
    """
    Model field that stores Python dict as JSON dump.

    Also on converting value from dump to Python field uses
    ``AVAILABLE_SETTINGS`` container to coerce stored values to real Python
    objects.

    You should set custom encoder class for dumps Python object to JSON data
    via ``encoder_cls`` keyword argument. By default, ``DjangoJSONEncoder``
    would be used.
    """
    default = dict
    __metaclass__ = SubfieldBase
    
    def __init__(self, *args, **kwargs):
        """
        Initialize settings field. Add support of ``encoder_cls`` keyword arg.
        """
        self.encoder_cls = kwargs.pop('encoder_cls', DjangoJSONEncoder)
        super(SettingsField, self).__init__(*args, **kwargs)

    def clean(self, value, instance, settings=None):
        """
        Run validation for each setting value.
        """
        data = {} if not value else value
        settings = settings or AVAILABLE_SETTINGS

        for name, value in data.items():
            if not hasattr(settings, name):
                continue

            mixed = getattr(settings, name)

            if is_settings_container(mixed):
                data[name] = self.clean(value, instance, mixed)
            else:
                data[name] = mixed.to_field(initial=value).clean(value)

        return data

    def contribute_to_class(self, cls, name):
        super(SettingsField, self).contribute_to_class(cls, name)

        def get_json(model):
            return self.get_db_prep_value(getattr(model, self.attname))
        setattr(cls, 'get_%s_json' % self.name, get_json)

        def set_json(model, json):
            setattr(model, self.attname, self.to_python(json))
        setattr(cls, 'set_%s_json' % self.name, set_json)

    def get_default(self):
        if self.has_default():
            if callable(self.default):
                return self.default()
            return self.default
        return super(SettingsField, self).get_default()

    def get_prep_value(self, value):
        return simplejson.dumps(value, cls=self.encoder_cls)

    def to_python(self, value):
        if not isinstance(value, basestring):
            return value

        if value == '':
            return value

        try:
            data = simplejson.loads(value,
                                    encoding=django_settings.DEFAULT_CHARSET)
        except ValueError:
            # If string could not parse as JSON it's means that it's Python
            # string saved to SettingsField.
            return value

        return self._settings_to_python(data)

    def from_db_value(self, value, expression, connection, context):
        return self.to_python(value)

    def _settings_to_python(self, data, settings=None):
        settings = settings or AVAILABLE_SETTINGS

        for key, value in data.items():
            if hasattr(settings, key):
                mixed = getattr(settings, key)

                if is_settings_container(mixed):
                    data[key] = self._settings_to_python(value, mixed)
                else:
                    data[key] = mixed.to_python(value)

        return data


# Add suport of SettingsField for South
def add_south_introspector_rules():
    rules = [((SettingsField, ), [], {})]
    add_introspection_rules(rules, ['^setman\.fields'])


try:
    from south.modelsinspector import add_introspection_rules
except ImportError:
    pass
else:
    add_south_introspector_rules()
