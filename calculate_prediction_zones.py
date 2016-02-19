# -------------------------------------------------------------------------------
# Name:         calculate_prediction_zones.py
#
# Purpose:      Calculate a probability surface showing the liklihood of the
#               occurance of a repeat or near repeat incident
#
# Author:       Allison Muise
#
# Created:     04/02/2016
# -------------------------------------------------------------------------------

import arcpy
from datetime import date

# Enable overwriting datasets
arcpy.env.overwriteOutput = True


def expand_extents(data, stretch):
    """Expand the extents of a dataset by a set distance in all directions by
        adding and removing features from the dataset"""

    # Calculate new dataset extents from current values
    d = arcpy.Describe(data)

    xmin = d.extent.XMin - stretch
    ymax = d.extent.YMax + stretch

    new_features = [(xmin, d.extent.YMin - stretch),
                    (d.extent.XMax + stretch, ymax)]

    # Add two features to the dataset at the new xmin, ymin and xmax, ymax
    with arcpy.da.InsertCursor(data, ['Shape@X', 'Shape@Y']) as cursor:
        for feat in new_features:
            cursor.insertRow(feat)

    # Delete the two new features based on their coordinate values
    with arcpy.da.UpdateCursor(data, ['Shape@X', 'Shape@Y']) as rows:
        for row in rows:
            if row[0] == xmin or row[1] == ymax:
                rows.deleteRow()


def main(in_features, date_field, spatial_band_size, temporal_band_size,
         probability_type, slice_num='', out_raster, out_polygon, *args):

    """ Generates a raster and series of polygons based on that raster to
        illustrate the probability of incidents occuring at the current moment
        in time based on defined algoritms for the decay of spatial and temporal
        influence of previous incidents.

        in_features: Point feature class showign the location of incidents that
                     have occured recently, and from which predictions will be
                     based. This feature class must have a date field and all
                     features must have date values.

        date_field: Field in in_features containing the date each incident
                    occurred. Values in this field are used to calculate the
                    decay of temporal influence between when the incident
                    occured and the current date.

        spatial_band_size: Value in the units of in_features representing the
                           maximum reach of spatial influence of historical
                           incidents.

        temporal_band_size: Value in days representing the maximum reach of
                            temporal influence of historical incidents.
                            Features in in_features where todays date minus the
                            incident date results in a number of days greater
                            than this value will not be considered when
                            creating the prediction zones.

        probability_type: 'CUMULATIVE' (default) creates a surface resulting
                          from summing the prediction risks from each incident;
                          'MAXIMUM' creates a surface representing the maximum
                          risk value from each incident.

        slice_num: Integer value representing the number of zones that will be
                   created from the prediction raster. Each zone will represent
                   a range of prediction risk values.

        out_raster: Output incident prediction surface raster. Raster name will
                    have timestamp appended to avoid overwriting previous
                    rasters.

        out_polygon_fc: Output polygon feature class based on classifying the
                        out_raster values into slice_num categories.
                        Polygon boundaries represent the bounds of the
                        prediction zones as defined by the raster slices.
    """

    try:
        # Check out spatial analyst extentsion
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            raise Exception("Spatial Analyst license unavailable")

        # Work in an in-memory copy of the dataset to avoid editing the original
        incident_fc = arcpy.FeatureClassToFeatureClass_conversion(in_features,
                                                                  "in_memory",
                                                                  'temp_incs')

        # Get OID field name
        oidname = arcpy.Describe(incident_fc).oidFieldName

        # Expand the extents of the dataset by the size of the spatial band
        #   rasters will represent the full extent of risk,
        #   not bound to extents of incidents
        expand_extents(incident_fc, float(spatial_band_size))

        # SelectLayerByAttributes tool requires feature layer
        incident_lyr = arcpy.MakeFeatureLayer_management(incident_fc)

        # Create summary raster with max extents
        d = arcpy.Describe(incident_fc)
        sum_raster = arcpy.sa.CreateConstantRaster(0,
                                                   data_type='INTEGER',
                                                   extent=d.extent)

        arcpy.env.extent = d.extent

        # Get current date & time
##        today = datetime.datetime.today() # Data is old
        today = datetime.datetime.strptime("10/15/2009", "%m/%d/%Y")

        # Create spatial temporal rasters for each incident
        with arcpy.da.SearchCursor(incident_fc, ['OID@', date_field]) as incidents:
            for incident in incidents:

                # Calculate age of incident
                date_diff = today - incident[1]

                # Don't process incidents outisde reack of temporal influence
                if date_diff.days > int(temporal_band_size):
                    continue

                # Build float distance raster for incident
                where_clause = """{} = {}""".format(oidname, incident[0])
                arcpy.SelectLayerByAttribute_management(incident_lyr,
                                                        where_clause=where_clause)
                dist_raster = arcpy.sa.EucDistance(incident_lyr,
                                                   spatial_band_size)
                inc_raster = arcpy.sa.Float(dist_raster)

                # Apply distance & temporal decay
                inc_raster = arcpy.sa.Plus(inc_raster, 1)

                # Process cumulative risk
                if probability_type == 'CUMULATIVE':
                    sum_raster = arcpy.sa.Plus(sum_raster, inc_raster)

                # Process maximum risk
                else:
                    # Determine cells where sum raster has => value
                    sum_vals = arcpy.sa.GreaterThanEqual(sum_raster, inc_raster)
                    sum_vals = arcpy.sa.Times(sum_vals, sum_raster)

                    # Determine cells where inc raster has greater value
                    inc_vals = arcpy.sa.GreaterThan(inc_raster, sum_raster)
                    inc_vals = arcpy.sa.Times(inc_vals, inc_raster)

                    # Sum greatest value rasters
                    sum_raster = arcpy.sa.Plus(sum_vals, inc_vals)

        # Save final probability raster
        if not slice_num:
            sum_raster.save(out_raster)

        # Optionally convert to polygons - Slice + Raster to Polygon?
        else:
            slice_raster = arcpy.sa.Slice(sum_raster, int(slice_num))
            risk_polys = arcpy.RasterToPolygon_conversion(slice_raster,
                                                          out_polygon)

        # Optionally publish raster - overwrite or new service?

    except Exception as ex:
        print(ex)
    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
    finally:
        arcpy.CheckInExtension("Spatial")


if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    main(*argv)
