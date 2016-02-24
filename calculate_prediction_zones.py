# -----------------------------------------------------------------------------
# Name:         calculate_prediction_zones.py BETA
#
# Purpose:      Calculate a probability surface showing the liklihood of the
#               occurance of a repeat or near repeat incident
#
# Author:       Esri., Inc.
#
# Created:     04/02/2016
# -----------------------------------------------------------------------------

import arcpy

from datetime import datetime as dt
from datetime import timedelta as td
from os import path
import os

from arcrest.security import AGOLTokenSecurityHandler
from arcresthelper import securityhandlerhelper
from arcresthelper import common
from arcrest.agol import FeatureLayer

# Enable overwriting datasets
arcpy.env.overwriteOutput = True

# Status fields for output polygons (created if non-existant)
cur_status_field = 'MOSTRECENT'
cur_date_field = 'CREATEDATE'

# TODO: Get current date & time
today = dt.today()
##today = dt.strptime("12/15/2009", "%m/%d/%Y")

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

# End of expand_extents function


def connect_to_layer(username, password, server_url, service_url):
    """Connect to ArcGIS Online or Portal for ArcGIS layer"""
    proxy_port = None
    proxy_url = None

    si = {}
    si['security_type'] = 'Portal'  # LDAP, NTLM, OAuth, Portal, PKI
    si['username'] = username
    si['password'] = password
    si['org_url'] = server_url
    si['proxy_url'] = proxy_url
    si['proxy_port'] = proxy_port
    si['referer_url'] = None
    si['token_url'] = None
    si['certificatefile'] = None
    si['keyfile'] = None
    si['client_id'] = None
    si['secret_id'] = None

    shh = securityhandlerhelper.securityhandlerhelper(securityinfo=si)
    if not shh.valid:
        raise Exception(shh.message)

    fl = FeatureLayer(
        url=service_url,
        securityHandler=shh.securityhandler,
        proxy_port=proxy_port,
        proxy_url=proxy_url,
        initialize=True)

    return fl

# End of connect_to_layer function


def calculate_risk_surface(lyr, age, dist):
    """Create raster of risk extent and intensity based on incident age and
       spatial reach of influence"""

    # Build float distance raster for incident
    dist_raster = arcpy.sa.EucDistance(lyr,
                                       dist)

    # Apply distance & temporal decay
    inc_raster = (float(dist) - (dist_raster + 1.0)) * (float(2) / float(age + 1))

    # Set Null values to 0 to allow for raster math
    null_locations = arcpy.sa.IsNull(inc_raster)
    inc_raster = arcpy.sa.Con(null_locations, 0,
                              inc_raster, where_clause="Value = 1")
    return inc_raster

# End of calculate_risk_surface function


def calculate_max_risk(cumulative_raster, new_raster):
    """Creates a raster using the maximum values of two rasters"""
    # Determine cells where sum raster has => value
    sum_vals = arcpy.sa.GreaterThanEqual(cumulative_raster, new_raster)
    sum_vals = arcpy.sa.Times(sum_vals, cumulative_raster)

    # Determine cells where inc raster has greater value
    inc_vals = arcpy.sa.GreaterThan(new_raster, cumulative_raster)
    inc_vals = arcpy.sa.Times(inc_vals, new_raster)

    # Sum greatest value rasters
    cumulative_raster += inc_vals

    return cumulative_raster

# End of calculate_max_risk function


def add_status_fields_to_lyr(lyr):
    """Adds a text and/or date field to a fc or lyr for tracking status"""
    fields = [f.name for f in arcpy.ListFields(lyr)]

    if cur_status_field not in fields:
        arcpy.AddField_management(lyr, cur_status_field, 'TEXT', field_length=5)

    if cur_date_field not in fields:
        arcpy.AddField_management(lyr, cur_date_field, 'DATE')

# End of add_status_fields_to_lyr function


def add_status_field_to_service(fl):
    """Adds a text and/or date field to a hosted service for tracking status"""
    layer_fields = [f['name'] for f in fl.fields]
    fieldToAdd = {"fields": []}

    if cur_status_field not in layer_fields:
        fieldToAdd["fields"].append({
                "name": cur_status_field,
                "type": "esriFieldTypeString",
                "alias": cur_status_field,
                "sqlType": "sqlTypeOther",
                "length": 5,
                "nullable": True,
                "editable": True,
                "domain": None,
                "defaultValue": None})

    if cur_date_field not in layer_fields:
        fieldToAdd["fields"].append({
                "name": cur_date_field,
                "type": "esriFieldTypeDate",
                "alias": cur_date_field,
                "nullable": True,
                "editable": True,
                "domain": None,
                "defaultValue": None})

    fl.administration.addToDefinition(fieldToAdd)

# End of add_status_field_to_service function


def convert_raster_to_zones(raster, bins, status_field, date_field):
    """Convert non-0 raster cell values to polygons using a
       set number of bins"""
    sliced = arcpy.sa.Slice(raster, int(bins))
    polys = arcpy.RasterToPolygon_conversion(sliced,
                                             path.join("in_memory",
                                                       "temp_polys"),
                                             "NO_SIMPLIFY")
    add_status_fields_to_lyr(polys)

    with arcpy.da.UpdateCursor(polys, [status_field, date_field]) as rows:
        for row in rows:
            row[0] = 'True'
            row[1] = today
            rows.updateRow(row)

    return polys

# End of convert_raster_to_zones function


def create_zone_fc(template, sr, out_path):
    """Create polygon feature class for prediction zone features"""
    poly_paths = out_path.split(os.sep)[:-1]
    poly_path = os.sep.join(poly_paths)
    poly_name = out_path.split(os.sep)[-1]

    arcpy.CreateFeatureclass_management(poly_path,
                                        poly_name,
                                        template=template)
    arcpy.DefineProjection_management(out_path, sr)

    return out_path

# End of create_zone_fc function


def main(in_features, date_field, spatial_band_size, temporal_band_size,
         probability_type, slice_num, out_raster, out_polygon,
         pub_polys='', pub_type='', username='', password='',
         server_url='', poly_url='', *args):

    """ Generates a raster and series of polygons based on that raster to
        illustrate the probability of incidents occuring at the current moment
        in time based on defined algorithms for the decay of spatial and
        temporal influence of previous incidents.

        in_features: Point feature class showing the location of incidents that
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

        pub_polys: booleen option for publishing the polygon features. Service
                   must exist previously. Service will be truncated and the
                   cumulative results from in_features will be appended

        pub_type: Choice of publication environments- NONE, ARCGIS_ONLINE,
                  ARCGIS_PORTAL, ARCGIS_SERVER

        username: administrative username for the services

        password: corresponding to the username

        server_url: organization url

        poly_url: URL to the rest endpoint of the polygon service layer
    """

    try:
        # Check out spatial analyst extentsion
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            raise Exception("Spatial Analyst license unavailable")

        now = dt.strftime(dt.now(), "%Y_%m_%d_%H_%M_%S")

        # Convert booleen values
        if not pub_polys == 'True':
            pub_polys = False

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

        # Create in-memory summary raster with max extents
        d = arcpy.Describe(incident_fc)
        sr = d.spatialReference
        arcpy.env.extent = d.extent

        sum_raster = arcpy.sa.CreateConstantRaster(0, data_type='INTEGER',
                                                   extent=d.extent)

        # Calculate minimum bounds of accepted time frame
        date_min = today - td(days=int(temporal_band_size))

        # Create risk rasters for each incident within temporal reach of today
        sql = """{0} <= date'{1}' AND {0} >= date'{2}'""".format(date_field,
                                                                 today,
                                                                 date_min)

        with arcpy.da.SearchCursor(incident_fc,
                                   ['OID@', date_field],
                                   where_clause=sql) as incidents:

            for incident in incidents:

                # Calculate age of incident
                date_diff = today - incident[1]

                # Build float distance raster for incident
                sql = """{} = {}""".format(oidname, incident[0])
                arcpy.SelectLayerByAttribute_management(incident_lyr,
                                                        where_clause=sql)

                inc_raster = calculate_risk_surface(incident_lyr,
                                                    date_diff.days,
                                                    spatial_band_size)

                # Process cumulative risk
                if probability_type == 'CUMULATIVE':
                    sum_raster += inc_raster

                # Process maximum risk
                else:
                    sum_raster = calculate_max_risk(sum_raster, inc_raster)

        # Save final probability raster where values are > 0
        sum_raster = arcpy.sa.SetNull(sum_raster, sum_raster, "Value <= 0")
        sum_raster.save('_'.join([out_raster, now]))

        # Slice raster values into categories and convert to temp polys
        temp_polys = convert_raster_to_zones(sum_raster, slice_num,
                                             cur_status_field, cur_date_field)

        # Creat polygon fc if it doesn't exist
        if not arcpy.Exists(out_polygon):
            create_zone_fc(temp_polys, sr, out_polygon)

        # Create status fields if they don't exist
        add_status_fields_to_lyr(out_polygon)

        # Set status of all existing features to False
        sql = """{} <> 'False'""".format(cur_status_field)
        with arcpy.da.UpdateCursor(out_polygon,
                                   cur_status_field,
                                   where_clause=sql) as rows:
            for row in rows:
                row[0] = 'False'
                rows.updateRow(row)

        # Append temp poly features to output polygon fc
        arcpy.Append_management(temp_polys, out_polygon)

        # Update polygon services.
        # If pubtype = NONE or SERVER, no steps necessary
        if pub_type in ['ARCGIS_ONLINE', 'ARCGIS_PORTAL'] and pub_polys:

            # connect to incidents service
            try:
                fl = connect_to_layer(username, password, server_url, poly_url)
            except:
                raise Exception('Could not connect to service. Please verify organization URL and service URL are correct, and the provided username and password have access to the service.')

            # Check service for status and creation fields - add if necessary
            add_status_field_to_service(fl)

            # Update 'current' features in service to be 'past'
            field_info = [{'FieldName': cur_status_field,
                           'ValueToSet': 'False'}]

            out_fields = ['objectid']
            for fld in field_info:
                out_fields.append(fld['FieldName'])

            sql = """{} = 'True'""".format(cur_status_field)
            updateFeats = fl.query(where=sql,
                                   out_fields=','.join(out_fields))

            for feat in updateFeats:
                for fld in field_info:
                    feat.set_value(fld['FieldName'], fld['ValueToSet'])

            fl.updateFeature(features=updateFeats)

            # Add new 'current' features
            fl.addFeatures(temp_polys)

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
