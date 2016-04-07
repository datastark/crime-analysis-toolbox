[New to Github? Get started here.]: http://htmlpreview.github.com/?https://github.com/Esri/esri.github.com/blob/master/help/esri-getting-to-know-github.html
[ArcGIS for Local Government maps and apps]: http://solutions.arcgis.com/local-government
[guidelines for contributing]: https://github.com/esri/contributing
[LICENSE.txt]: LICENSE.txt

# crime-analysis-toolbox

The Crime Analysis Toolbox contains a series of tools for identifying and analyzing patterns in incident data

####Note to Beta Testers:
In the latest version of the Crime Analysis Toolbox we have added a folder called Utilities, under which there is a new tool called Export Incidents to CSV. This tool allows you to quickly and easily export incident data from ArcGIS for use in the Near Repeat Calculator (to determine the statistical significance of your repeat and near repeat patterns).  The tool requires you to:
-	Identify the feature class containing the incident data you wish to export
-	Identify the field containing the date of the incident (i.e., the committed from date of the incident)
-	Specify the location and the name of the CSV file that is to be exported.

The CSV file will contain three columns: X and Y coordinates for your incident data (based on the projected geographic coordinate system of the data) and the date of the incident.  The CSV file can then be opened directly in the Near Repeat Calculator without any further manipulation.

We hope you find this tool useful and look forward to your feedback.


## Tools
* Incident Classification tool: Identify originating, repeat, or near-repeat incidents and view their connections in time and space.
* Prediction Zone tool: Identify areas most at risk for repeat and near-repeat incidents, and update a service with these areas.
* Export Incidents to CSV: Exports a feature class to a csv file in the format required by the Near Repeat Calculator

## Requirements

### Experience

* Authoring maps
* Running geoprocessing tools
* Publishing services

### Software
* ArcMap 10.3.1+ or ArcGIS Pro 1.2+ with Advanced license
* Spatial Analyst extension
* Python 2.7 or 3.4

## Instructions

### General Help
* [New to Github? Get started here.][]

## Resources

Learn more about Esri's [ArcGIS for Local Government maps and apps][].

## Issues

Find a bug or want to request a new feature?  Please let us know by submitting an issue.

## Contributing

Esri welcomes contributions from anyone and everyone. Please see our [guidelines for contributing][].

## Licensing

Copyright 2016 Esri

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

A copy of the license is available in the repository's [LICENSE.txt][] file.

[](Esri Tags: ArcGISSolutions Local-Government)
[](Esri Language: Python)
