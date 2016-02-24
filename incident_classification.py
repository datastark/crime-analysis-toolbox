# -----------------------------------------------------------------------------
# Name: incident_classification.py
#
# Purpose: Classify incidents according to spatial and temporal proximity to
#          preceeding incidents. Generate a summary report of the processed
#          incidents
#
# Author: Esri., Inc.
#
# Created: 06/02/2016
#
# -----------------------------------------------------------------------------

import arcpy
from datetime import datetime as dt
from datetime import timedelta as td
from os.path import join


# Added field names
spatial_band_field = 'SPATIALBAND'
temporal_band_field = 'TEMPORALBAND'
incident_type_field = 'INCCLASS'
origin_feat_field = 'ORIGIN'


def reset_fields(fc):
    """Checks for required incident classification fields,
       and deletes/adds fields as necessary"""

    # Delete classification fields if they already exist in the dataset
    inc_fields = [f.name for f in arcpy.ListFields(fc)]

    delete_fields = []

    for field in[spatial_band_field, temporal_band_field, incident_type_field]:
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

    # Add field for temporal band
    arcpy.AddField_management(fc,
                              field_name=temporal_band_field,
                              field_type='FLOAT')

    # Add field for ID of associated origin feature
    arcpy.AddField_management(fc,
                              field_name=origin_feat_field,
                              field_type='LONG')


def calculate_band(value, bands):
    """Finds the first number in a list larger than a value"""
    for band in bands:
        if band > value:
            return tband


def classify_incidents(in_features, date_field, spatial_bands, temporal_bands,
                       repeatdist=0, report_location, *args):
    """Updates an input feature class to classify features according to their
       proximity in space and time to previous incidents

       in_features: point feature class of incidents to classify. This dataset
                    will typically cover a large timespan. Must have a date field.

       report_location: Directory on disk where a summary report (csv) of the
                        processed incidents can be written.

       date_field: Field of type Date on the in_features dataset.
                   All features must have values in this field.

       spatial_bands: semi-colon separated list of distances in the unit of the
                      in_features. Features will be classified according to
                      the smallest value that exceeds their proximity in space
                      to the nearest preceeding incident that is also within the
                      maximum allowable temporal_band value.

       temporal_bands: semi-colon separated list of positive integers
                       representing the number of days between an originating
                       incident and a repeat or near repeat incident. Features
                       will be classified according to the smallest listed value
                       that exceeds their proximity in time to their nearest
                       spatial neighbour.

       repeatdist: Distance in the units of in_features below which adjacent
                   incidents are considered repeats rather than near-repeats.
                   Default value is 0."""

    # Build sorted lists of band values
    spatial_bands = [float(b) for b in spatial_bands.split(';')]
    temporal_bands = [float(b) for b in temporal_bands.split(';')]
    spatial_bands.sort()
    temporal_bands.sort()

    # Convert repeat distance value to a number
    repeatdist = float(repeatdist)

    # Report run time used for file names etc
    now = dt.strftime(dt.now(), "%Y-%m-%d_%H-%M-%S")

    # Check for and delete existing fields necessary for classification
    reset_fields(in_features)

    # Get name of OID field
    oidname = arcpy.Describe(in_features).oidFieldName

    # Get sorted list of unique incident date values
    with arcpy.da.SearchCursor(in_features, date_field) as rows:
        date_vals = []
        for row in rows:
            date_vals.append(row[0])
    date_vals = list(set(date_vals))
    date_vals.sort()

    # Range of incident dates
    min_date = date_vals[0]
    max_date = date_vals[-1]

    # List to store id of each type of feature
    origin_ids = []
    repeat_ids = []
    nearrepeat_ids = []

    # For each date, starting with the oldest
    for date_val in date_vals:
        print ''
        print date_val

        # Create layer of potential R/NR for which an O incident will be sought
        where_clause = """{} = date'{}'""".format(date_field, date_val)
        rnr_features = arcpy.MakeFeatureLayer_management(all_incs, where_clause)

        # Select potential O based on max historical temporal band
        t_max = date_val
        t_min = date_val - td(days=temporal_bands[-1])

        where_clause = """{0} < date'{1}' AND {0} >= date'{2}'""".format(date_field,
                                                                         t_max,
                                                                         t_min)
        o_features = arcpy.MakeFeatureLayer_management(spat_features,
                                                       where_clause)

        # Find potential originator incident nearest each rpt/near rpt inc
        arcpy.Near_analysis(rnr_features,
                            o_features,
                            search_radius=spatial_bands[-1],
                            method='GEODESIC')

        # Add values to lists of IDs NR, and R features based on proximity to
        # potential originators, and mark as originators those features which
        # are identified as having (near) repeats
        fields = ["OID@", "NEAR_FID", "NEAR_DIST", incident_type_field,
                  spatial_band_field, temporal_band_field, origin_feat_field,
                  date_field]
        with arcpy.da.UpdateCursor(rnr_features, fields, """NEAR_FID > 0""") as nearfeats:
            for nearfeat in nearfeats:

                # Record origin feature
                origin_ids.append(str(nearfeat[1]))

                # Classify repeat feature
                if nearfeat[2] <= repeatdist:
                    nearfeat[3] = 'R'

                # Classify near repeat feature and save origin id
                else:
                    nearfeat[3] = 'NR'

                    # Save origin ID
                    nearfeat[6] = nearfeat[1]

                # Classify spatial band
                nearfeat[7] = calculate_band(nearfeat[2], spatial_bands)

                # Classify temporal band
                where_clause = """{} = {}""".format(oidname, nearfeat[0])
                with arcpy.da.SearchCursor(o_features, ['OID@', date_field], where_clause) as ofeats:
                    for ofeat in ofeats:
                        odate = ofeat[1]

                datediff = nearfeat[7] - odate

                nearfeat[5] = calculate_band(datediff.days(), temporal_bands)

                # Save updates
                nearfeats.updateRow(nearfeat)

        # Delete near fields
        arcpy.DeleteField_management(temp_features, 'NEAR_FID;NEAR_DIST')

    # Classify features identified as originators
    if origin_ids:
        oids = ','.join(origin_ids)
        arcpy.SelectLayerByAttribute_management(in_features,
                                                'NEW_SELECTION',
                                                '{} IN ({})'.format(oidname,
                                                                    oids))
        arcpy.CalculateField_management(in_features,
                                        incident_type_field,
                                        "'O'",
                                        'PYTHON')
        # TODO: update calc to consider features that are R and NR already

    # Calculate the frequency of incidents in each band
    inc_cnt = 0
    orig_cnt = 0
    rpt_cnt = 0
    nrpt_cnt = 0

    # Build empty dictionary to hold tallies
    band_counts = {}
    for sband in spatial_bands:
        band_counts[sband] = {}
        for tband in temporal_bands:
            band_counts[sband][tband] = 0

    # Count number of incidents that fall into each category
    # TODO: update to include all categories
    where_clause = """{} IS NOT NULL""".format(incident_type_field)
    fields = [incident_type_field, spatial_band_field, temporal_band_field]
    with arcpy.da.SearchCursor(in_features, fields, where_clause) as rows:
        for row in rows:
            inc_cnt += 1
            if 'O' in row[0]:
                orig_cnt += 1
            else:
                band_counts[row[1]][row[2]] += 1

            if 'NR' in row[0]:
                nrpt_cnt += 1
            elif 'R' in row[0]:
                rpt_cnt += 1

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
    for sband in band_counts:
        band_count = '{}'.format(sband)
        band_perc = '{}'.format(sband)
        vals = band_counts[sband]
        for tband in vals:
            band_count += ',{}'.format(vals[tband])
            band_perc += ',{}'.format(100*vals[tband]/inc_cnt)
        counts_table += '{}\n'.format(band_count)
        percent_table += '{}\n'.format(band_perc)

    # Write report
    reportname = join(report_location, "{}_{}.csv".format('Summary', now))
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


if __name__ == '__main__':
    argv = tuple(arcpy.GetParameterAsText(i)
                 for i in range(arcpy.GetArgumentCount()))
    classify_incidents(*argv)
