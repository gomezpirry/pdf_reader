# PDF Reader

Read a pdf document and extract labels and text of form

## Requeriments

* __pdfminer:__ a tool for extracting information from PDF documents
* __unidecode:__ a tool for representing unicode data in ASCII characters
* __requests:__ a tool for HTTP requests
* __Pillow:__ a Python image library

## Installation

`pip install pdfminer unidecode requests Pillow`

## Usage

* Process pdf file and get labels and text (store in python dictionary)

`python pdf_reader.py path_to_pdf_file`

### Output 

* csv file with page, labels for page and text associated to label
* csv file of annotations (biontology api)

