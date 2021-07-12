import importlib
import re
import unittest

from natcap.invest import cli
import pint


valid_nested_types = {
    'all': {
        'boolean',
        'code',
        'csv',
        'directory',
        'file',
        'freestyle_string',
        'number',
        'option_string',
        'percent',
        'raster',
        'ratio',
        'vector',
    },
    'raster': {'code', 'number', 'ratio'},
    'vector': {
        'code',
        'freestyle_string',
        'number',
        'option_string',
        'percent',
        'ratio'},
    'csv': {
        'boolean',
        'code',
        'freestyle_string',
        'number',
        'option_string',
        'percent',
        'raster',
        'ratio',
        'vector'},
    'directory': {'csv', 'directory', 'file', 'raster', 'vector'}
}


class ValidateArgsSpecs(unittest.TestCase):

    def test_model_specs(self):

        for model_name, val in cli._MODEL_UIS.items():
            # val is a collections.namedtuple, fields accessible by name
            model = importlib.import_module(val.pyname)

            # validate that each arg meets the expected pattern
            # save up errors to report at the end
            for key, arg in model.ARGS_SPEC['args'].items():
                # the top level should have 'name' and 'about' attrs
                # but they aren't required at nested levels
                self.validate(
                    arg,
                    f'{model_name}.{key}',
                    valid_types=valid_nested_types['all'],
                    required_attrs=['name', 'about'])

    def validate(self, arg, name, valid_types, is_pattern=False, required_attrs=[]):
        """
        Recursively validate nested args against the ARGS_SPEC standard.

        Args:
            arg (dict): any nested arg component of an ARGS_SPEC
            name (str): name to use in error messages to identify the arg
            valid_types (list[str]): a list of the arg types that are valid
                for this nested arg (due to its parent's type).
            is_pattern (bool): if True, the arg is validated as a pattern (such
                as for user-defined  CSV headers, vector fields, or directory
                paths).
            required_attrs (list[str]): a list of attributes that must be in
                the arg dictionary regardless of type

        Returns:
            None

        Raises:
            AssertionError if the arg violates the standard
        """
        with self.subTest(nested_arg_name=name):
            for attr in required_attrs:
                self.assertTrue(attr in arg)

            # arg['type'] can be either a string or a set of strings
            types = arg['type'] if isinstance(
                arg['type'], set) else [arg['type']]
            attrs = set(arg.keys())
            for t in types:
                self.assertTrue(t in valid_types)

                if t == 'option_string':
                    # option_string type should have an options property that
                    # describes the valid options
                    self.assertTrue('options' in arg)
                    # May be a set or dict because some option sets are self
                    # explanatory and others need a description
                    self.assertTrue(isinstance(arg['options'], dict) or
                                    isinstance(arg['options'], set))
                    if isinstance(arg['options'], set):
                        for item in arg['options']:
                            self.assertTrue(isinstance(item, str))
                    else:
                        for key, val in arg['options'].items():
                            self.assertTrue(isinstance(key, str))
                            self.assertTrue(isinstance(val, str))
                    attrs.remove('options')

                elif t == 'freestyle_string':
                    # freestyle_string may optionally have a regexp attribute
                    # this is a regular expression that the string must match
                    if 'regexp' in arg:
                        self.assertTrue(isinstance(arg['regexp'], str))
                        re.compile(arg['regexp'])  # should be regex compilable
                        attrs.remove('regexp')

                elif t == 'number':
                    # number type should have a units property
                    self.assertTrue('units' in arg)
                    # Undefined units should use the custom u.none unit
                    self.assertTrue(isinstance(arg['units'], pint.Unit))
                    attrs.remove('units')

                    # number type may optionally have an 'expression' attribute
                    # this is a string expression to be evaluated with the
                    # intent of determining that the value is within a range.
                    # The expression must contain the string ``value``, which
                    # will represent the user-provided value (after it has been
                    # cast to a float).  Example: "(value >= 0) & (value <= 1)"
                    if 'expression' in arg:
                        self.assertTrue(isinstance(arg['expression'], str))
                        attrs.remove('expression')

                elif t == 'raster':
                    # raster type should have a bands property that maps each band
                    # index to a nested type dictionary describing the band's data
                    self.assertTrue('bands' in arg)
                    self.assertTrue(isinstance(arg['bands'], dict))
                    for band in arg['bands']:
                        self.assertTrue(isinstance(band, int))
                        self.validate(
                            arg['bands'][band],
                            f'{name}.bands.{band}',
                            valid_types=valid_nested_types['raster'])
                    attrs.remove('bands')

                    # may optionally have a 'projected' attribute that says
                    # whether the raster must be linearly projected
                    if 'projected' in arg:
                        self.assertTrue(isinstance(arg['projected'], bool))
                        attrs.remove('projected')
                    # if 'projected' is True, may also have a 'projection_units'
                    # attribute saying the expected linear projection unit
                    if 'projection_units' in arg:
                        # doesn't make sense to have projection units unless
                        # projected is True
                        self.assertTrue(arg['projected'])
                        self.assertTrue(
                            isinstance(arg['projection_units'], pint.Unit))
                        attrs.remove('projection_units')

                elif t == 'vector':
                    # vector type should have:
                    # - a fields property that maps each field header to a nested
                    #   type dictionary describing the data in that field
                    # - a geometries property: the set of valid geometry types
                    self.assertTrue('fields' in arg)
                    self.assertTrue(isinstance(arg['fields'], dict))
                    for field in arg['fields']:
                        self.assertTrue(isinstance(field, str))
                        self.validate(
                            arg['fields'][field],
                            f'{name}.fields.{field}',
                            valid_types=valid_nested_types['vector'])

                    self.assertTrue('geometries' in arg)
                    self.assertTrue(isinstance(arg['geometries'], set))

                    attrs.remove('fields')
                    attrs.remove('geometries')

                    # may optionally have a 'projected' attribute that says
                    # whether the vector must be linearly projected
                    if 'projected' in arg:
                        self.assertTrue(isinstance(arg['projected'], bool))
                        attrs.remove('projected')
                    # if 'projected' is True, may also have a 'projection_units'
                    # attribute saying the expected linear projection unit
                    if 'projection_units' in arg:
                        # doesn't make sense to have projection units unless
                        # projected is True
                        self.assertTrue(arg['projected'])
                        self.assertTrue(
                            isinstance(arg['projection_units'], pint.Unit))
                        attrs.remove('projection_units')

                elif t == 'csv':
                    # csv type should have a rows property, columns property, or
                    # neither. rows or columns properties map each expected header
                    # name/pattern to a nested type dictionary describing the data
                    # in that row/column. may have neither if the table structure
                    # is too complex to describe this way.
                    has_rows = 'rows' in arg
                    has_cols = 'columns' in arg
                    # should not have both
                    self.assertTrue(not (has_rows and has_cols))

                    if has_cols or has_rows:
                        direction = 'rows' if has_rows else 'columns'
                        headers = arg[direction]
                        self.assertTrue(isinstance(headers, dict))

                        for header in headers:
                            self.assertTrue(isinstance(header, str))
                            self.validate(
                                headers[header],
                                f'{name}.{direction}.{header}',
                                valid_types=valid_nested_types['csv'])

                        attrs.discard('rows')
                        attrs.discard('columns')

                    # csv type may optionally have an 'excel_ok' attribute
                    if 'excel_ok' in arg:
                        self.assertTrue(isinstance(arg['excel_ok'], bool))
                        attrs.discard('excel_ok')

                elif t == 'directory':
                    # directory type should have a contents property that maps each
                    # expected path name/pattern within the directory to a nested
                    # type dictionary describing the data at that filepath
                    self.assertTrue('contents' in arg)
                    self.assertTrue(isinstance(arg['contents'], dict))
                    for path in arg['contents']:
                        self.assertTrue(isinstance(path, str))
                        self.validate(
                            arg['contents'][path],
                            f'{name}.contents.{path}',
                            valid_types=valid_nested_types['directory'])
                    attrs.remove('contents')

                    # may optionally have a 'permissions' attribute, which is a
                    # string of the unix-style directory permissions e.g. 'rwx'
                    if 'permissions' in arg:
                        self.validate_permissions_value(arg['permissions'])
                        attrs.remove('permissions')
                    # may optionally have an 'must_exist' attribute, which says
                    # whether the directory must already exist
                    # this defaults to True
                    if 'must_exist' in arg:
                        self.assertTrue(isinstance(arg['must_exist'], bool))
                        attrs.remove('must_exist')

                elif t == 'file':
                    # file type may optionally have a 'permissions' attribute
                    # this is a string listing the permissions e.g. 'rwx'
                    if 'permissions' in arg:
                        self.validate_permissions_value(arg['permissions'])

            # iterate over the remaining attributes
            # type-specific ones have been removed by this point
            if 'name' in attrs:
                self.assertTrue(isinstance(arg['name'], str))
                attrs.remove('name')
            if 'about' in attrs:
                self.assertTrue(isinstance(arg['about'], str))
                attrs.remove('about')
            if 'required' in attrs:
                # required value may be True, False, or a string that can be
                # parsed as a python statement that evaluates to True or False
                self.assertTrue(isinstance(arg['required'], bool) or
                                isinstance(arg['required'], str))
                attrs.remove('required')
            if 'type' in attrs:
                self.assertTrue(isinstance(arg['type'], str) or
                                isinstance(arg['type'], set))
                attrs.remove('type')

            # args should not have any unexpected properties
            # all attrs should have been removed by now
            if attrs:
                raise AssertionError(f'{name} has key(s) {attrs} that are not '
                                     'expected for its type')

    def validate_permissions_value(self, permissions):
        """
        Validate an rwx-style permissions string.

        Args:
            permissions (str): a string to validate as permissions

        Returns:
            None

        Raises:
            AssertionError if `permissions` isn't a string, if it's
            an empty string, if it has any letters besides 'r', 'w', 'x',
            or if it has any of those letters more than once
        """

        self.assertTrue(isinstance(permissions, str))
        self.assertTrue(len(permissions) > 0)
        valid_letters = {'r', 'w', 'x'}
        for letter in permissions:
            self.assertTrue(letter in valid_letters)
            # should only have a letter once
            valid_letters.remove(letter)


if __name__ == '__main__':
    unittest.main()