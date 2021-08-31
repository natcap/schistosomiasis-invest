import json

import pint


# the same unit registry instance should be shared across everything
u = pint.UnitRegistry()

# Custom unit definitions #####################################################

# see https://pint.readthedocs.io/en/stable/defining.html
# pint doesn't allow multiple base units for the same dimension
# but you can define mutliple dimensionless units with []
# https://github.com/hgrecco/pint/issues/1278
u.define('currency = [value]')    # non-specific unit of value
u.define('pixel = []')            # non-specific unit of area
# used in coastal vulnerability, the DEM pixel values measure
# elevation (length) but the specific units don't matter
# and in the rec model for cell size
u.define('linear_unit = []')  # non-specific unit of length
# add "us_survey_foot" on to the aliases because it's used in some rasters
u.define('survey_foot = 1200 / 3937 * meter = sft = us_survey_foot')
# Vitamin A in the crop production nutrient table is measured in IUs
# A special unit in pharmacology that measures biologically active substances
# May be converted to weight or volume, but conversion factors are specific
# to the substance. I couldn't find a definition of its dimensionality.
u.define('international_unit = [biologic_amount] = iu = IU')
# use 'h' not 'hr' as the symbol for hour, as per SI guidelines
# overwrite the default use of the symbol 'h' for henries
u.define('henry = weber / ampere')
u.define('hour = 60 * minute = h = hr')
# overwrite the year definition to use 'year' rather than 'a' as default symbol
# the symbol 'yr' is english-specific and the international symbol 'a' may
# not be well-known, so we will need to translate this
u.define('year = 365.25 * day = _ = yr = a = julian_year')
# Use u.none for unitless measurements
u.define('none = []')


# Specs for common arg types ##################################################
WORKSPACE = {
    "name": "workspace",
    "about": (
        "The folder where all the model's output files will be written. If "
        "this folder does not exist, it will be created. If data already "
        "exists in the folder, it will be overwritten."),
    "type": "directory",
    "contents": {},
    "must_exist": False,
    "permissions": "rwx",
}

SUFFIX = {
    "name": "file suffix",
    "about": (
        "Suffix that will be appended to all output file names. Useful to "
        "differentiate between model runs."),
    "type": "freestyle_string",
    "required": False,
    "regexp": "[a-zA-Z0-9_-]*"
}

N_WORKERS = {
    "name": "taskgraph n_workers parameter",
    "about": (
        "The n_workers parameter to provide to taskgraph. "
        "-1 will cause all jobs to run synchronously. "
        "0 will run all jobs in the same process, but scheduling will take "
        "place asynchronously. Any other positive integer will cause that "
        "many processes to be spawned to execute tasks."),
    "type": "number",
    "units": u.none,
    "required": False,
    "expression": "value >= -1"
}

METER_RASTER = {
    "type": "raster",
    "bands": {
        1: {
            "type": "number",
            "units": u.meter
        }
    }
}
AOI = {
    "type": "vector",
    "fields": {},
    "geometries": {"POLYGON", "MULTIPOLYGON"},
    "name": "area of interest",
    "about": (
        "A polygon vector containing features over which to aggregate and "
        "summarize the final results."),
}
LULC = {
    "type": "raster",
    "bands": {1: {"type": "integer"}},
    "about": "Map of land use/land cover codes.",
    "name": "land use/land cover"
}
DEM = {
    "type": "raster",
    "bands": {
        1: {
            "type": "number",
            "units": u.meter
        }
    },
    "about": "Map of elevation above sea level.",
    "name": "digital elevation model"
}
PRECIP = {
    "type": "raster",
    "bands": {
        1: {
            "type": "number",
            "units": u.millimeter/u.year
        }
    },
    "about": "Map of average annual precipitation.",
    "name": "precipitation"
}
ETO = {
    "name": "evapotranspiration",
    "type": "raster",
    "bands": {
        1: {
            "type": "number",
            "units": u.millimeter
        }
    },
    "about": "Map of evapotranspiration values."
}
SOIL_GROUP = {
    "type": "raster",
    "bands": {1: {"type": "integer"}},
    "about": (
        "Map of soil hydrologic groups. Pixels may have values 1, 2, 3, or 4, "
        "corresponding to soil hydrologic groups A, B, C, or D, respectively."
    ),
    "name": "soil hydrologic group"
}
THRESHOLD_FLOW_ACCUMULATION = {
    "expression": "value >= 0",
    "type": "number",
    "units": u.pixel,
    "about": (
        "The number of upstream pixels that must flow into a pixel "
        "before it is classified as a stream."),
    "name": "threshold flow accumulation"
}

REQUIRED_IF_SELECTED = 'Required if %s is selected.'
REQUIRED_IF_PROVIDED = 'Required if %s is provided.'
RASTER_VALUES = 'All values in this raster must have corresponding entries in the %s table.'

# geometry types ##############################################################
# the full list of ogr geometry types is in an enum in
# https://github.com/OSGeo/gdal/blob/master/gdal/ogr/ogr_core.h

POINT = {'POINT'}
LINESTRING = {'LINESTRING'}
POLYGON = {'POLYGON'}
MULTIPOINT = {'MULTIPOINT'}
MULTILINESTRING = {'MULTILINESTRING'}
MULTIPOLYGON = {'MULTIPOLYGON'}

LINES = LINESTRING | MULTILINESTRING
POLYGONS = POLYGON | MULTIPOLYGON
POINTS = POINT | MULTIPOINT
ALL_GEOMS = LINES | POLYGONS | POINTS


def format_unit(unit):
    """Represent a pint Unit as user-friendly unicode text.

    This attempts to follow the style guidelines from the NIST
    Guide to the SI (https://www.nist.gov/pml/special-publication-811):
    - Use standard symbols rather than spelling out
    - Use '/' to represent division
    - Use the center dot ' · ' to represent multiplication
    - Combine denominators into one, surrounded by parentheses

    Args:
        unit (pint.Unit): the unit to format

    Raises:
        TypeError if unit is not an instance of pint.Unit.

    Returns:
        String describing the unit.
    """
    if not isinstance(unit, pint.Unit):
        raise TypeError(
            f'{unit} is of type {type(unit)}. '
            f'It should be an instance of pint.Unit')

    # Optionally use a pre-set format for a particular unit
    custom_formats = {
        # For soil erodibility (t*h*ha/(ha*MJ*mm)), by convention the ha's
        # are left on top and bottom and don't cancel out
        # pint always cancels units where it can, so add them back in here
        # this isn't a perfect solution
        # see https://github.com/hgrecco/pint/issues/1364
        u.t * u.hr / (u.MJ * u.mm): 't · h · ha / (ha · MJ · mm)'
    }
    if unit in custom_formats:
        return custom_formats[unit]

    # look up the abbreviated symbol for each unit
    # `formatter` expects an iterable of (unit, exponent) pairs, which lives in
    # the pint.Unit's `_units` attribute.
    unit_items = [(u.get_symbol(key), val) for key, val in unit._units.items()]
    return pint.formatting.formatter(
        unit_items,
        as_ratio=True,
        single_denominator=True,
        product_fmt=" · ",
        division_fmt='/',
        power_fmt="{}{}",
        parentheses_fmt="({})",
        exp_call=pint.formatting._pretty_fmt_exponent)


def serialize_args_spec(spec):
    """Serialize an ARGS_SPEC dict to a JSON string.

    Args:
        spec (dict): An invest model's ARGS_SPEC.

    Raises:
        TypeError if any object type within the spec is not handled by
        json.dumps or by the fallback serializer.

    Returns:
        JSON String
    """

    def fallback_serializer(obj):
        """Serialize objects that are otherwise not JSON serializeable."""
        if isinstance(obj, pint.Unit):
            return format_unit(obj)
        # Sets are present in 'geometries' attributes of some args
        # We don't need to worry about deserializing back to a set/array
        # so casting to string is okay.
        elif isinstance(obj, set):
            return str(obj)
        raise TypeError(f'fallback serializer is missing for {type(obj)}')

    return json.dumps(spec, default=fallback_serializer)
