# -----------------------------------------------------------------------------
# Name:         calculate_prediction_zones.py
#
# Purpose:      Calculate a probability surface showing the liklihood of the
#               occurance of a repeat or near repeat incident
#
# Author:       Allison Muise
#
# Created:     04/02/2016
# -----------------------------------------------------------------------------

# D:\CrimeAnalysis\TestData.gdb\TwoWeeks Date_ 1000 14 CUMULATIVE 5 D:\CrimeAnalysis\TestData.gdb\testraster D:\CrimeAnalysis\TestData.gdb\testpolys2 True False ARCGIS_ONLINE amuise_lg pigsfly http://arcgis4localgov2.maps.arcgis.com http://services.arcgis.com/b6gLrKHqgkQb393u/arcgis/rest/services/TestPolys/FeatureServer/0

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

cur_status_field = 'MOSTRECENT'
cur_date_field = 'CREATEDATE'

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


def connect_to_layer(username, password, server_url, service_url):
    proxy_port = None
    proxy_url = None

    securityinfo = {}
    securityinfo['security_type'] = 'Portal'#LDAP, NTLM, OAuth, Portal, PKI
    securityinfo['username'] = username
    securityinfo['password'] = password
    securityinfo['org_url'] = server_url
    securityinfo['proxy_url'] = proxy_url
    securityinfo['proxy_port'] = proxy_port
    securityinfo['referer_url'] = None
    securityinfo['token_url'] = None
    securityinfo['certificatefile'] = None
    securityinfo['keyfile'] = None
    securityinfo['client_id'] = None
    securityinfo['secret_id'] = None

    shh = securityhandlerhelper.securityhandlerhelper(securityinfo=securityinfo)
    if shh.valid == False:
        raise Exception(shh.message)

    fl = FeatureLayer(
        url=service_url,
        securityHandler=shh.securityhandler,
        proxy_port=proxy_port,
        proxy_url=proxy_url,
        initialize=True)

    return fl


def main(in_features, date_field, spatial_band_size, temporal_band_size,
         probability_type, slice_num, out_raster, out_polygon,
         pub_polys, pub_raster, pub_type,
         username, password, server_url, poly_url, *args):

    """ Generates a raster and series of polygons based on that raster to
        illustrate the probability of incidents occuring at the current moment
        in time based on defined algorithms for the decay of spatial and temporal
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
        pub_polys: booleen option for publishing the polygon features. Service
                   must exist previously. Service will be truncated and the
                   cumulative results from in_features will be appended
        pub_raster: booleen option for publishing the raster.
        pub_type: Choice of publication environments- NONE, ARCGIS_ONLINE,
                  ARCGIS_PORTAL, ARCGIS_SERVER
        username: administrative usernmae for the services
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
        if not pub_raster == 'True':
            pub_raster = False

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
        arcpy.env.extent = d.extent

        sum_raster = arcpy.sa.CreateConstantRaster(0,
                                                   data_type='INTEGER',
                                                   extent=d.extent)

        # TODO: Get current date & time
##        today = dt.today() # Data is old
        today = dt.strptime("11/15/2009", "%m/%d/%Y")
        date_min = today - td(days=int(temporal_band_size))

        where_clause = """{0} <= date'{1}' AND {0} >= date'{2}'""".format(date_field, today, date_min)

        # Create spatial temporal rasters for each incident
        with arcpy.da.SearchCursor(incident_fc, ['OID@', date_field], where_clause=where_clause) as incidents:
            for incident in incidents:

                # Calculate age of incident
                date_diff = today - incident[1]

                # Build float distance raster for incident
                where_clause = """{} = {}""".format(oidname, incident[0])
                arcpy.SelectLayerByAttribute_management(incident_lyr,
                                                        where_clause=where_clause)
                dist_raster = arcpy.sa.EucDistance(incident_lyr,
                                                   spatial_band_size)
                inc_raster = arcpy.sa.Float(dist_raster)

                # Apply distance & temporal decay
                inc_raster = arcpy.sa.Plus(inc_raster, 1)
                inc_raster = arcpy.sa.Minus(float(spatial_band_size),
                                            inc_raster)

                # Set Null values to 0 to allow for raster math
                null_locations = arcpy.sa.IsNull(inc_raster)
                inc_raster = arcpy.sa.Con(null_locations, 0,
                                          inc_raster, where_clause="Value = 1")

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
        sum_raster = arcpy.sa.SetNull(sum_raster, sum_raster, "Value <= 0")
        out_raster = '_'.join([out_raster, now])
        sum_raster.save(out_raster)

        # Slice raster values into categories and convert to temp polys
        slice_raster = arcpy.sa.Slice(sum_raster, int(slice_num))
        temp_polys = arcpy.RasterToPolygon_conversion(slice_raster,
                                                      path.join("in_memory",
                                                                "temp_polys"),
                                                      "NO_SIMPLIFY")
        arcpy.AddField_management(temp_polys,
                                  cur_status_field,
                                  'TEXT',
                                  field_length=5)

        arcpy.AddField_management(temp_polys,
                                  cur_date_field,
                                  'DATE')

        with arcpy.da.UpdateCursor(temp_polys, [cur_status_field, cur_date_field]) as rows:
            for row in rows:
                row[0] = 'True'
                row[1] = today
                rows.updateRow(row)

        # Creat polygon fc if it doesn't exist
        if not arcpy.Exists(out_polygon):
            poly_paths = out_polygon.split(os.sep)[:-1]
            poly_path = os.sep.join(poly_paths)
            poly_name = out_polygon.split(os.sep)[-1]

            arcpy.CreateFeatureclass_management(poly_path,
                                                poly_name,
                                                template=temp_polys)

        # Create status field if it doesn't exist
        if cur_status_field not in [f.name for f in arcpy.ListFields(out_polygon)]:
            arcpy.AddField_management(out_polygon,
                                      cur_status_field,
                                      'TEXT',
                                      field_length=5)

        arcpy.AddField_management(out_polygon,
                                  cur_date_field,
                                  'DATE')

        # Set status of all existing features to False
        where_clause = """{} <> 'False'""".format(cur_status_field)
        with arcpy.da.UpdateCursor(out_polygon, cur_status_field) as rows:
            for row in rows:
                row[0] = 'False'
                rows.updateRow(row)

        # Append temp poly features to output polygon fc
        arcpy.Append_management(temp_polys, out_polygon)

        # Update polygon services.
        # If pubtype = NONE or SERVER, no steps necessary
        if pub_type in ['ARCGIS_ONLINE', 'ARCGIS_PORTAL'] and pub_polys:

            # connect to incidents service
            fl = connect_to_layer(username, password, server_url, poly_url)

            # Check service for status and creation fields - add if necessary
            layer_fields = [f['name'] for f in fl.fields]
            fieldToAdd = {"fields": []}

            if not cur_status_field in layer_fields:
                fieldToAdd["fields"].append({
                        "name" : cur_status_field,
                        "type" : "esriFieldTypeString",
                        "alias" : cur_status_field,
                        "sqlType" : "sqlTypeOther", "length" : 5,
                        "nullable" : True,
                        "editable" : True,
                        "domain" : None,
                        "defaultValue" : None})

            if not cur_date_field in layer_fields:
                fieldToAdd["fields"].append({
                        "name" : cur_date_field,
                        "type" : "esriFieldTypeDate",
                        "alias" : cur_date_field,
                        "nullable" : True,
                        "editable" : True,
                        "domain" : None,
                        "defaultValue" : None})

            fl.administration.addToDefinition(fieldToAdd)

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
