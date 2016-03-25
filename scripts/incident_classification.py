# -----------------------------------------------------------------------------
# Copyright 2015 Esri
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------

# D:\CrimeAnalysis\testData.gdb\SpencerData newdates D:\CrimeAnalysis\output 1000;750;500;250 28;7;14;21 10 D:\CrimeAnalysis\testData.gdb connectiontest D:\CrimeAnalysis\testData.gdb\SpencerData

# ==================================================
# incident_classification.py BETA
# --------------------------------------------------
# requirments: ArcMap/ArcCatalog 10.3.1+
#              ArcGIS Pro 1.2+
#              ArcGIS Advanced license required
#              Python 2.7 or 3.4
# author: ArcGIS Solutions
# contact: ArcGISTeamLocalGov@esri.com
# company: Esri
# ==================================================
# description: Classify incidents according to spatial and temporal proximity
#              to preceeding incidents. Generate a summary report of the
#              processed incidents
# ==================================================
# history:
# 03/23/2016 - AM - beta
# ==================================================

import arcpy
from datetime import datetime as dt
from datetime import timedelta as td
from os import path
##import traceback

# Added field names
spatial_band_field = 'SPATIALBAND'
temporal_band_field = 'TEMPORALBAND'
incident_type_field = 'INCCLASS'
origin_feat_field = 'ORIGIN'
z_value_field = 'ZVALUE'


def reset_fields(fc):
    """Checks for required incident classification fields,
       and deletes/adds fields as necessary"""

    # Delete classification fields if they already exist in the dataset
    inc_fields = [f.name for f in arcpy.ListFields(fc)]

    delete_fields = []

    for field in['NEAR_FID', 'NEAR_DIST', 'DISTTOORIG', spatial_band_field,
                 temporal_band_field, incident_type_field, origin_feat_field,
                 z_value_field]:
        if field in inc_fields:
            delete_fields.append(field)

    if delete_fields:
        arcpy.DeleteField_management(fc, delete_fields)

    # Add field for incident classification
    arcpy.AddField_management(fc,
                              field_name=incident_type_field,
                              field_type='TEXT')

    # Add field for spatial band
    arcpy.AddField_management(fc,
                              field_name=spatial_band_field,
                              field_type='FLOAT')
    # Add field for distance to origin
    arcpy.AddField_management(fc,
                              field_name="DISTTOORIG",
                              field_type='FLOAT')

    # Add field for temporal band
    arcpy.AddField_management(fc,
                              field_name=temporal_band_field,
                              field_type='FLOAT')

    # Add field for ID of associated origin feature
    arcpy.AddField_management(fc,
                              field_name=origin_feat_field,
                              field_type='LONG')

    # Add field for z value calculation
    arcpy.AddField_management(fc,
                              field_name=z_value_field,
                              field_type='LONG')


def calculate_band(value, bands):
    """Finds the first number in a list larger than a value"""
    for band in bands:
        if band > value:
            return band


def classify_incidents(in_features, date_field, report_location, spatial_bands,
                       temporal_bands, repeatdist, out_lines_dir, out_lines_name,
                       *args):
    """Updates an input feature class to classify features according to their
       proximity in space and time to previous incidents

       in_features: point feature class of incidents to classify. This dataset
                    will typically cover a large timespan. Must have a date
                    field.

       date_field: Field of type Date on the in_features dataset.
                   All features must have values in this field.

       report_location: Directory on disk where a summary report (csv) of the
                        processed incidents can be written.

       spatial_bands: semi-colon separated list of distances in the unit of the
                      in_features. Features will be classified according to
                      the smallest value that exceeds their proximity in space
                      to the nearest preceeding incident that is also within
                      the maximum allowable temporal_band value.

       temporal_bands: semi-colon separated list of positive integers
                       representing the number of days between an originating
                       incident and a repeat or near repeat incident. Features
                       will be classified according to the smallest listed
                       value that exceeds their proximity in time to their
                       nearest spatial neighbour.

       repeatdist: Distance in the units of in_features below which adjacent
                   incidents are considered repeats rather than near-repeats.
                   Default value is 0.

       out_lines_dir: The workspace where the line features will be stored

       out_lines_name: The name of the feature class that will be created to
                       hold the line features."""
    try:
        # Build sorted lists of band values
        spatial_bands = [float(b) for b in spatial_bands.split(';')]
        temporal_bands = [float(b) for b in temporal_bands.split(';')]

        repeatdist = float(repeatdist)
        spatial_bands.append(repeatdist)

        spatial_bands.sort()
        temporal_bands.sort()

        arcpy.env.overwriteOutput = True

        # Report run time used for file names etc
        now = dt.strftime(dt.now(), "%Y-%m-%d_%H-%M-%S")

        # Check for and delete existing fields necessary for classification
        reset_fields(in_features)

        # Get name of OID field
        oidname = arcpy.Describe(in_features).oidFieldName

        # Get sorted list of unique incident date values
        with arcpy.da.SearchCursor(in_features, date_field) as rows:
            date_vals = [row[0] for row in rows]

        date_vals = list(set(date_vals))
        date_vals.sort()

        # Range of incident dates
        min_date = date_vals[0]
        max_date = date_vals[-1]

        # Find nearest feature within the max spatial and temporal windows
        for date_val in date_vals:

            # Create layer of potential R/NR for which an O incident will be sought
            where_clause = """{} = date'{}'""".format(date_field, date_val)
            rnr_features = arcpy.MakeFeatureLayer_management(in_features,
                                                             'rnr_features',
                                                             where_clause)

            # Select potential O based on max historical temporal band
            t_max = date_val
            t_min = date_val - td(days=temporal_bands[-1])

            where_clause = """{0} <= date'{1}' AND {0} > date'{2}'""".format(date_field,
                                                                             t_max,
                                                                             t_min)
            o_features = arcpy.MakeFeatureLayer_management(in_features,
                                                           'o_features',
                                                           where_clause)

            # Find originator incident nearest each rpt/near rpt inc
            arcpy.Near_analysis(rnr_features,
                                o_features,
                                search_radius=spatial_bands[-1],
                                method='GEODESIC')

            where_clause = """{0} >= {1} AND {0} <= {2}""".format("NEAR_DIST",
                                                                  0,
                                                                  spatial_bands[-1])
            arcpy.SelectLayerByAttribute_management(rnr_features,
                                                    where_clause=where_clause)
            arcpy.CalculateField_management(rnr_features, 'DISTTOORIG',
                                            '!NEAR_DIST!', 'PYTHON_9.3')
            arcpy.CalculateField_management(rnr_features, origin_feat_field,
                                            '!NEAR_FID!', 'PYTHON_9.3')

        # Process points identified as having originating features
        oids = []
        rnrids = []

        fields = ["OID@", origin_feat_field, "DISTTOORIG", incident_type_field,
                  spatial_band_field, temporal_band_field, date_field,
                  z_value_field, 'SHAPE@X', 'SHAPE@Y']

        # Prepare to insert line features
        new_lines = []

        with arcpy.da.UpdateCursor(in_features, fields) as nearfeats:
            for nearfeat in nearfeats:

                fid = nearfeat[0]
                oid = nearfeat[1]
                incident_date = nearfeat[6]
                temporal_band = nearfeat[5]

                z_value = incident_date - min_date
                nearfeat[7] = z_value.days

                if not nearfeat[1]:
                    pass

                elif nearfeat[1] > 0:

                    # Get origin feature attributes
                    where_clause = """{} = {}""".format(oidname, oid)
                    fields = ['OID@', date_field, 'SHAPE@X', 'SHAPE@Y']
                    with arcpy.da.SearchCursor(in_features, fields, where_clause) as ofeats:
                        for ofeat in ofeats:
                            odate = ofeat[1]
                            o_x = ofeat[2]
                            o_y = ofeat[3]

                    # Calculate location of incidents in time progression
                    o_z_value = odate - min_date

                    # Calculate days between incidents
                    datediff = incident_date - odate

                    # Classify spatial band
                    nearfeat[4] = calculate_band(nearfeat[2], spatial_bands)

                    # Classify temporal band
                    nearfeat[5] = calculate_band(datediff.days, temporal_bands)

                    # Save to identify ultimate origin features
                    oids.append(oid)
                    rnrids.append(fid)

                    # Save line segment
                    end = arcpy.Point(X=nearfeat[8], Y=nearfeat[9], Z=nearfeat[7])
                    start = arcpy.Point(X=o_x, Y=o_y, Z=o_z_value.days)
                    vertices = arcpy.Array([start, end])
                    feature = arcpy.Polyline(vertices, None, True, False)
                    new_lines.append([datediff.days, feature])

                # Save updates
                nearfeats.updateRow(nearfeat)

        # Create feature class for connecting lines
        sr = arcpy.Describe(in_features).spatialReference
        connectors = arcpy.CreateFeatureclass_management(out_lines_dir,
                                                         out_lines_name,
                                                         'POLYLINE',
                                                         has_z='ENABLED',
                                                         spatial_reference=sr)
        arcpy.AddField_management(connectors, 'RPTDAYS', "LONG")

        with arcpy.da.InsertCursor(connectors, ['RPTDAYS', 'SHAPE@']) as rows:
            for new_line in new_lines:
                rows.insertRow(new_line)

        # Record the frequency of incidents in each band
        inc_cnt = 0
        orig_cnt = 0
        rpt_cnt = 0
        nrpt_cnt = 0

        # Build empty dictionary to hold spatial and temporal band tallies
        band_counts = {}
        for sband in spatial_bands:
            band_counts[sband] = {}
            for tband in temporal_bands:
                band_counts[sband][tband] = 0

        # Classify & count incidents by type and band
        origins = list(set(oids) - set(rnrids))
        fields = ["OID@", 'DISTTOORIG', incident_type_field, origin_feat_field,
                  spatial_band_field, temporal_band_field]

        with arcpy.da.UpdateCursor(in_features, fields) as rows:
            for row in rows:
                if row[0] in origins:
                    row[2] = 'O'
                    orig_cnt += 1
                elif not row[3]:
                    pass
                elif row[3] > 0:
                    if not row[4]:
                        pass
                    elif row[1] <= repeatdist:
                        row[2] = 'R'
                        rpt_cnt += 1
                    else:
                        row[2] = 'NR'
                        nrpt_cnt += 1
                    band_counts[row[4]][row[5]] += 1

                inc_cnt += 1

                rows.updateRow(row)

        # Delete near fields
        arcpy.DeleteField_management(in_features, 'NEAR_FID;NEAR_DIST')

        # Build report content
        perc_o = 100*orig_cnt/inc_cnt
        perc_nr = 100*nrpt_cnt/inc_cnt
        perc_r = 100*rpt_cnt/inc_cnt

        report_header = ('Repeat and Near Repeat Incident Summary\n'
                         'Created {}\n'.format(now))

        data_info = ('Data Source: {}\n'
                     'Date Range: {}-{}\n'.format(in_features, min_date, max_date))

        inc_type_report = ('Count and percentage of each type of incident\n'
                           ', Count, Percentage\n'
                           'All Incidents,{}, 100\n'
                           'Originators,{},{}\n'
                           'Near Repeats,{},{}\n'
                           'Repeats,{},{}\n'.format(inc_cnt,
                                                    orig_cnt, perc_o,
                                                    nrpt_cnt, perc_nr,
                                                    rpt_cnt, perc_r))

        temp_band_strs = [str(b) for b in temporal_bands]
        temporal_band_labels = ','.join(temp_band_strs)
        counts_header = ('Number of Repeat and Near-Repeat incidents per spatial and temporal band\n'
                         ',{}\n'.format(temporal_band_labels))
        percent_header = ('Percentage of all incidents classified as Repeat or Near-Repeat and appearing in each spatial and temporal band\n'
                          ',{}\n'.format(temporal_band_labels))

        counts_table = ""
        percent_table = ""
        for sband in spatial_bands:
            # row leader
            band_count = str(sband)
            band_perc = str(sband)

            # get temporal bands and their incident counts
            vals = band_counts[sband]

            # Get spatial band count in each temporal band
            for tband in temporal_bands:
                band_count += ',{}'.format(vals[tband])
                band_perc += ',{}'.format(100*vals[tband]/inc_cnt)

            # append counts to the table
            counts_table += '{}\n'.format(band_count)
            percent_table += '{}\n'.format(band_perc)

        # Write report
        reportname = path.join(report_location, "{}_{}.csv".format('Summary', now))
        with open(reportname, 'w') as report:

            report.write(report_header)
            report.write('\n')
            report.write(data_info)
            report.write('\n')
            report.write(inc_type_report)
            report.write('\n')
            report.write(counts_header)
            report.write(counts_table)
            report.write('\n')
            report.write(percent_header)
            report.write(percent_table)

        arcpy.SetParameterAsText(9, path.join(out_lines_dir, out_lines_name))
        arcpy.AddMessage("View incident summary report: {}".format(reportname))


    except arcpy.ExecuteError:
        # Get the tool error messages
        msgs = arcpy.GetMessages()
        arcpy.AddError(msgs)
        print(msgs)

    except:
        # Return  error messages for use in script tool or Python Window
        arcpy.AddError(str(sys.exc_info()[1]))

        # Print Python error messages for use in Python / Python Window
        print(str(sys.exc_info()[1]) + "\n")


if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    classify_incidents(*argv)
