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

# ==================================================
# near_repeat_export.py BETA
# --------------------------------------------------
# requirments: ArcMap/ArcCatalog 10.3.1+
#              ArcGIS Pro 1.2+
#              Python 2.7 or 3.4
# author: ArcGIS Solutions
# contact: ArcGISTeamLocalGov@esri.com
# company: Esri
# ==================================================
# description: Create a csv file of the format required by the near repeat
#              calculator
# ==================================================
# history:
# 04/06/2016 - AM - beta
# ==================================================

import arcpy
from os import path

def classify_incidents(in_features, date_field, out_dir, out_csv, *args):
    """Creates a csv file of the format required by the near repeat calculator

       in_features: point feature class of incidents. This dataset will
                    typically cover a large timespan. Must have a date field.
                    Must be in a projected coordinate system

       date_field: Field of type Date on the in_features dataset.
                   All features must have values in this field.

       out_dir: Directory on disk where a the csv file will be written

       out_csv: Name of the generated csv file"""
    try:
    # Create csv file
        reportname = path.join(out_dir, "{}.csv".format(out_csv))
        with open(reportname, 'w') as report:

            # Read each record from the feature class
            sql = """{} IS NOT NULL""".format(date_field)
            fields = ['SHAPE@X', 'SHAPE@Y', date_field]
            with arcpy.da.SearchCursor(in_features, field_names=fields,
                                       where_clause=sql) as rows:
                for row in rows:
                    report.write('{},{},{},\n'.format(row[0],
                                                      row[1],
                                                      row[2].date(),
                                                      '\n'))
        arcpy.SetParameterAsText(4, reportname)

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
