"""InVEST Crop Production Percentile Model."""
import os
import logging

import numpy
from osgeo import gdal
import pygeoprocessing

from . import utils

logging.basicConfig(format='%(asctime)s %(name)-20s %(levelname)-8s \
%(message)s', level=logging.DEBUG, datefmt='%m/%d/%Y %H:%M:%S ')

LOGGER = logging.getLogger('natcap.invest.crop_production')

_OUTPUT_BASE_FILES = {
    }

_INTERMEDIATE_BASE_FILES = {
    }

_TMP_BASE_FILES = {
    }

_YIELD_PERCENTILE_FIELD_PATTERN = 'yield_([^_]+)'

_EXPECTED_NUTRIENT_TABLE_HEADERS = [
    'Protein', 'Lipid', 'Energy', 'Ca', 'Fe', 'Mg', 'Ph', 'K', 'Na', 'Zn',
    'Cu', 'Fl', 'Mn', 'Se', 'VitA', 'betaC', 'alphaC', 'VitE', 'Crypto',
    'Lycopene', 'Lutein', 'betaT', 'gammaT', 'deltaT', 'VitC', 'Thiamin',
    'Riboflavin', 'Niacin', 'Pantothenic', 'VitB6', 'Folate', 'VitB12',
    'VitK']
_NODATA_CLIMATE_BIN = 255
_NODATA_YIELD = -1.0


def execute(args):
    """Crop Production Percentile Model.

    This model will take a landcover (crop cover?) map and produce yields,
    production, and observed crop yields, a nutrient table, and a clipped
    observed map.

    Parameters:
        args['workspace_dir'] (string): output directory for intermediate,
            temporary, and final files
        args['results_suffix'] (string): (optional) string to append to any
            output file names
        args['landcover_raster_path'] (string): path to landcover raster
        args['landcover_to_crop_table_path'] (string): path to a table that
            converts landcover types to crop names that has two headers:
            * lucode: integer value corresponding to a landcover code in
              `args['landcover_raster_path']`.
            * crop_name: a string that must match one of the crops in
              args['global_data_path']/climate_bin_maps/[cropname]_*
              A ValueError is raised if strings don't match.
        args['global_data_path'] (string): path to the InVEST Crop Production
            global data directory.  This model expects that the following
            directories are subdirectories of this path
            * climate_bin_maps (contains [cropname]_climate_bin.tif files)
            * climate_percentile_yield (contains
              [cropname]_percentile_yield_table.csv files)

    Returns:
        None.
    """
    file_suffix = utils.make_suffix_string(args, 'results_suffix')

    intermediate_output_dir = os.path.join(
        args['workspace_dir'], 'intermediate_outputs')
    output_dir = os.path.join(args['workspace_dir'])
    utils.make_directories(
        [output_dir, intermediate_output_dir])

    f_reg = utils.build_file_registry(
        [(_OUTPUT_BASE_FILES, output_dir),
         (_INTERMEDIATE_BASE_FILES, intermediate_output_dir),
         (_TMP_BASE_FILES, output_dir)], file_suffix)

    landcover_raster_info = pygeoprocessing.get_raster_info(
        args['landcover_raster_path'])
    pixel_area_ha = numpy.product([
        abs(x) for x in landcover_raster_info['pixel_size']]) / 10000.0
    landcover_nodata = landcover_raster_info['nodata'][0]

    crop_to_landcover_table = utils.build_lookup_from_csv(
        args['landcover_to_crop_table_path'], 'crop_name', to_lower=True,
        numerical_cast=True)

    crop_lucode = None
    for crop_name in crop_to_landcover_table:
        crop_lucode = crop_to_landcover_table[crop_name]['lucode']
        print crop_name, crop_lucode
        crop_climate_bin_raster_path = os.path.join(
            args['global_data_path'], 'climate_bin_maps',
            '%s_climate_bin_map.tif' % crop_name)
        climate_percentile_yield_table_path = os.path.join(
            args['global_data_path'], 'climate_percentile_yield',
            '%s_percentile_yield_table.csv' % crop_name)
        if not os.path.exists(crop_climate_bin_raster_path):
            raise ValueError(
                "Expected climate bin map called %s for crop %s "
                "specified in %s", crop_climate_bin_raster_path, crop_name,
                args['landcover_to_crop_table_path'])
        if not os.path.exists(crop_climate_bin_raster_path):
            raise ValueError(
                "Expected climate bin map called %s for crop %s "
                "specified in %s", crop_climate_bin_raster_path, crop_name,
                args['landcover_to_crop_table_path'])

        local_climate_bin_raster_path = os.path.join(
            intermediate_output_dir,
            'local_%s_climate_bin_map%s.tif' % (crop_name, file_suffix))
        pygeoprocessing.warp_raster(
            crop_climate_bin_raster_path,
            landcover_raster_info['pixel_size'],
            local_climate_bin_raster_path, 'mode',
            target_sr_wkt=landcover_raster_info['projection'],
            target_bb=landcover_raster_info['bounding_box'])

        LOGGER.info("Mask out crop %s from landcover map", crop_name)

        masked_crop_raster_path = os.path.join(
            intermediate_output_dir, 'masked_climate_bin_map_%s%s.tif' % (
                crop_name, file_suffix))

        def _mask_climate_bin(lulc_array, climate_bin_array):
            """Mask in climate bins that intersect with `crop_lucode`."""
            result = numpy.empty(lulc_array.shape, dtype=numpy.int8)
            result[:] = _NODATA_CLIMATE_BIN
            valid_mask = lulc_array != landcover_nodata
            lulc_mask = lulc_array == crop_lucode
            result[valid_mask] = 0
            result[valid_mask & lulc_mask] = climate_bin_array[
                valid_mask & lulc_mask]
            return result

        pygeoprocessing.raster_calculator(
            [(args['landcover_raster_path'], 1),
             (local_climate_bin_raster_path, 1)],
            _mask_climate_bin, masked_crop_raster_path, gdal.GDT_Byte,
            _NODATA_CLIMATE_BIN)

        climate_percentile_table_path = os.path.join(
            args['global_data_path'], 'climate_percentile_yield',
            '%s_percentile_yield_table.csv' % crop_name)
        crop_climate_percentile_table = utils.build_lookup_from_csv(
            climate_percentile_table_path, 'climate_bin', to_lower=True,
            numerical_cast=True)

        yield_percentile_headers = [
            x for x in crop_climate_percentile_table.itervalues().next()
            if x != 'climate_bin']

        for yield_percentile_id in yield_percentile_headers:
            yield_percentile_raster_path = os.path.join(
                intermediate_output_dir, '%s_%s%s.tif' % (
                    crop_name, yield_percentile_id, file_suffix))

            bin_to_percentile_yield = dict([
                (bin_id,
                 crop_climate_percentile_table[bin_id][yield_percentile_id])
                for bin_id in crop_climate_percentile_table])
            bin_to_percentile_yield[0] = _NODATA_YIELD

            pygeoprocessing.reclassify_raster(
                (masked_crop_raster_path, 1), bin_to_percentile_yield,
                yield_percentile_raster_path, gdal.GDT_Float32,
                _NODATA_YIELD, exception_flag='values_required')

        LOGGER.info("Calculate observed yield for %s", crop_name)
        observed_yield_raster_path = os.path.join(
            args['global_data_path'], 'observed_yield',
            '%s_yield_map.tif' % crop_name)
        local_observed_yield_raster_path = os.path.join(
            intermediate_output_dir, '%s_local_observed_yield%s.tif' % (
                crop_name, file_suffix))
        pygeoprocessing.warp_raster(
            observed_yield_raster_path,
            landcover_raster_info['pixel_size'],
            local_observed_yield_raster_path, 'mode',
            target_sr_wkt=landcover_raster_info['projection'],
            target_bb=landcover_raster_info['bounding_box'])

        observed_yield_nodata = pygeoprocessing.get_raster_info(
            local_observed_yield_raster_path)['nodata'][0]
        def _mask_observed_yield(lulc_array, observed_yield_array):
            """Mask in climate bins that intersect with `crop_lucode`."""
            result = numpy.empty(lulc_array.shape, dtype=numpy.float32)
            result[:] = observed_yield_nodata
            valid_mask = lulc_array != landcover_nodata
            lulc_mask = lulc_array == crop_lucode
            result[valid_mask] = 0
            result[valid_mask & lulc_mask] = observed_yield_array[
                valid_mask & lulc_mask]
            return result

        local_observed_masked_yield_raster_path = os.path.join(
            intermediate_output_dir,
            '%s_local_observed_masked_yield%s.tif' % (crop_name, file_suffix))

        pygeoprocessing.raster_calculator(
            [(args['landcover_raster_path'], 1),
             (local_observed_yield_raster_path, 1)],
            _mask_observed_yield, local_observed_masked_yield_raster_path,
            gdal.GDT_Float32, observed_yield_nodata)

    nutrient_table = utils.build_lookup_from_csv(
        os.path.join(args['global_data_path'], 'nutrient_contents_table.csv'),
        'crop')

    LOGGER.info("Report table")
    result_table_path = os.path.join(
        output_dir, 'result_table%s.csv' % file_suffix)
    with open(result_table_path, 'wb') as result_table:
        result_table.write(
            'crop,' + ','.join(sorted(yield_percentile_headers)) +
            ',observed_production\n')
        for crop_name in sorted(crop_to_landcover_table):
            result_table.write(crop_name)
            print crop_name
            production_factor = pixel_area_ha * (
                1.0 - nutrient_table[crop_name]['fraction_refuse'])
            for yield_percentile_id in sorted(yield_percentile_headers):
                print yield_percentile_id
                yield_percentile_raster_path = os.path.join(
                    intermediate_output_dir, '%s_%s%s.tif' % (
                        crop_name, yield_percentile_id, file_suffix))
                yield_sum = 0.0
                for _, yield_block in pygeoprocessing.iterblocks(
                        yield_percentile_raster_path):
                    yield_sum += numpy.sum(
                        yield_block[_NODATA_YIELD != yield_block])
                print yield_sum
                production = yield_sum * production_factor
                result_table.write(",%f" % production)
            yield_sum = 0.0
            local_observed_masked_yield_raster_path = os.path.join(
                intermediate_output_dir,
                '%s_local_observed_masked_yield%s.tif' % (
                    crop_name, file_suffix))
            observed_yield_nodata = pygeoprocessing.get_raster_info(
                local_observed_masked_yield_raster_path)['nodata'][0]
            for _, yield_block in pygeoprocessing.iterblocks(
                    local_observed_masked_yield_raster_path):
                yield_sum += numpy.sum(
                    yield_block[observed_yield_nodata != yield_block])
            production = yield_sum * production_factor
            result_table.write(",%f" % production)
            result_table.write('\n')
