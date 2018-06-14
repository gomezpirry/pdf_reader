from pdfminer.pdfparser import PDFParser
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTFigure, LTImage, LTTextLine
from unidecode import unidecode
from PIL import Image
import cStringIO
import requests
import math
import time
import json
import sys
import os

horizontal_space = 210
vertical_offset = 5

# Bio-ontology Api params
api_url = 'http://data.bioontology.org/annotator'
api_key = ''
api_format = 'json'
api_ontology = 'DOID'
sections = ['Thematic Areas Addressed', 'Elevator pitch', 'Short Activity Description', 'Activity Description',
            'Knowledge triangle intregration', 'Link to Campus', 'Link to Accelerator', 'Societal Impact',
            'What added value does EIT Health provide?', 'Why are EIT Health resources needed for the Activity?',
            "Why is the Activity relevant for EIT Health's core mission?", "How will the Activity contribute to EIT Health's KPI's",
            'Innovative Outputs', 'Market Need', 'Estimated market size', 'Market introduction strategy / deployment plan',
            'Innovation barriers', 'TRL Before and After the Activity', 'SWOT', 'Technological Risk', 'Commercial Risk']
discarded_labels = ['disease']


class PdfMinerWrapper(object):
    """
    Usage:
    with PdfMinerWrapper('2009t.pdf') as doc:
        for page in doc:
           #do something with the page
    """

    def __init__(self, pdf_doc, pdf_pwd=""):
        self.pdf_doc = pdf_doc
        self.pdf_pwd = pdf_pwd

    def __enter__(self):
        # open the pdf file
        self.fp = open(self.pdf_doc, 'rb')
        # create a parser object associated with the file object
        parser = PDFParser(self.fp)
        # create a PDFDocument object that stores the document structure
        doc = PDFDocument(parser, password=self.pdf_pwd)
        # connect the parser and document objects
        parser.set_document(doc)
        self.doc = doc
        return self

    def _parse_pages(self):
        resource_manager = PDFResourceManager()
        la_params = LAParams(all_texts=True)
        device = PDFPageAggregator(resource_manager, laparams=la_params)
        interpreter = PDFPageInterpreter(resource_manager, device)

        for page in PDFPage.create_pages(self.doc):
            interpreter.process_page(page)
            # receive the LTPage object for this page
            layout = device.get_result()
            # layout is an LTPage object which may contain child objects like LTTextBox, LTFigure, LTImage, etc.
            yield layout

    def __iter__(self):
        return iter(self._parse_pages())

    def __exit__(self, _type, value, traceback):
        self.fp.close()


def get_text_pdf(pdf_file):
    text_dict = {}

    with PdfMinerWrapper(pdf_file) as doc:

        last_page = 1
        last_label = 1
        thematic_page = False
        thematic_index = None

        thematic_items = []
        thematic_checked = []

        # for each page in the document
        for page in doc:
            labels = []  # list for storing labels found

            # get labels
            # for each text box in page in x position lower than horizontal space
            for text_box in page:
                if text_box.bbox[0] < horizontal_space:
                    if not isinstance(text_box, LTTextBoxHorizontal):
                        continue
                    # end if
                    label = unidecode(text_box.get_text().replace('\n', ' '))
                    if 'Thematic Areas Addressed' in label:
                        thematic_page = True
                        thematic_index = len(labels)
                    labels.append([(text_box.bbox[3], label.replace(';', ' ')), ''])
                # end if
            # end for
            labels.append([(0, ''), ''])  # avoid overflow

            # get position of checked thematics
            if thematic_page:
                for layout_object in page:
                    if layout_object.bbox[0] > horizontal_space:
                        if isinstance(layout_object, LTFigure):
                            if labels[thematic_index][0][0] > layout_object.bbox[3] > labels[thematic_index + 1][0][0]:
                                parse_figure(layout_object, thematic_items)
                            # end if
                        # end if
                    # end if
                # end for
            # end if

            # associate text to labels
            # for each text box in page in x position greater than horizontal space
            for text_box in page:

                if text_box.bbox[0] > horizontal_space:
                    # review if is a text box
                    if not isinstance(text_box, LTTextBoxHorizontal):
                        continue
                    # end if

                    # pass text box with edit word (button text in document)
                    if unidecode(text_box.get_text().replace('\n', '')) == "Edit":
                        continue
                    # end if

                    # if page don't have labels, aggregate text to last label
                    if len(labels) == 1:
                        text_dict[last_page][last_label][1] += unidecode(text_box.get_text().replace('\n', ' '))
                        continue
                    # end if
                    found = False

                    # for each label in page
                    for i in xrange(0, len(labels) - 1):
                        # find associated label to text ( range between label and next label)
                        if labels[i][0][0] + vertical_offset > text_box.bbox[3] > labels[i + 1][0][0]:
                            if i == thematic_index and thematic_page:
                                parse_item(text_box, thematic_items, thematic_checked)
                                last_page = page.pageid
                                last_label = i
                                found = True
                                break
                            else:
                                labels[i][1] += ' ' + unidecode(text_box.get_text().replace('\n', ' '))
                                last_page = page.pageid
                                last_label = i
                                found = True
                                break
                        # end if
                    # end for

                    #
                    if not found and page.pageid > 1:
                        text_dict[last_page][last_label][1] += unidecode(text_box.get_text().replace('\n', ' '))
                    # end if
                # end if
            # end for
            if thematic_page:
                labels[thematic_index][1] += '. '.join(thematic_checked)
            thematic_page = False
            del labels[-1]
            text_dict[page.pageid] = labels
        # end for
    # end with

    return text_dict
# end def


def write_csv(csv_file, output_text):
    # write csv file
    file_form = open(csv_file, 'w')
    file_form.write('page; label; text\n')
    for key, value in output_text.iteritems():
        for label in value:
            file_form.write(str(key) + ';' + label[0][1] + ';' + label[1].replace(';', ' ') + '\n')
        file_form.write('\n')
    # end for
    file_form.close()
    # end if


def api_annotation(annotation_file, text_section, output_text, params=None):

    # csv file for annotations
    api_file = open(annotation_file, 'w')

    api_file.write('id; section; text; tags\n')
    document_id = ''

    # find document ID
    for value in output_text.itervalues():
        for label in value:
            if 'Generated Proposal ID'.lower() in label[0][1].lower():
                document_id = label[1]
                break

    # find section in document labels
    for section in text_section:
        for value in output_text.itervalues():
            for label in value:
                if label[0][1].replace(" ", '').lower() == section.replace(" ", '').lower():
                    api_file.write(document_id + ';' + label[0][1] + ';' + label[1].replace(';', ' ') + ';')
                    # set data params for api connection
                    data = params
                    data['text'] = label[1]
                    response = requests.post(api_url, json=data)
                    print label[0][1] + ': ' + str(requests.status_codes._codes[response.status_code][0])
                    # get response and extract information from json
                    if response.status_code == 200:
                        annotations = []
                        data = response.json()
                        for annotated_class in data:
                            class_url = annotated_class['annotatedClass']['links']['self']
                            pref_labels = []
                            text_pos = []
                            for note in annotated_class['annotations']:
                                text_pos.append((note['from'], note['to'], note['text']))
                            class_response = requests.get(class_url, json={'apikey': params['apikey']})
                            if class_response.status_code == 200:
                                class_json = class_response.json()
                                if not any(unidecode(class_json['prefLabel']) in s for s in discarded_labels):
                                    pref_labels.append(unidecode(class_json['prefLabel']))
                                for synonym in class_json['synonym']:
                                    if not any(unidecode(synonym) in s for s in discarded_labels):
                                        pref_labels.append(unidecode(synonym))
                            for word in text_pos:
                                text_fragment = label[1][word[0] - 1:word[1]]
                                for pref_label in pref_labels:
                                    if text_fragment == pref_label or text_fragment == pref_label.capitalize():
                                        annotations.append(pref_label)

                        api_file.write(', '.join(annotations))
                        break
                # end if
            # end for
        # end for
        api_file.write('\n')
    # end for
    api_file.close()
# end def


def is_valid_file(arg):
    if not os.path.exists(os.path.dirname(arg)):
        print ("The dir %s does not exist!" % os.path.dirname(arg))
        sys.exit()
    # end if


def parse_figure(layout_figure, items):
    """Function to recursively parse the layout figure tree."""
    # search area for gray pixels in the check box
    area = 3
    for lt_obj in layout_figure:
        if isinstance(lt_obj, LTImage):
            count_gray = 0
            # get LTImage and transform in PIL image
            img_stream = lt_obj.stream
            im = Image.open(cStringIO.StringIO(img_stream.get_rawdata()))
            im = im.convert('L')
            pixels = im.load()
            width, height = im.size
            done = False
            # check if the center of the image is a gray block
            number_white = math.ceil(((width/2 + area) - (width/2 - area) * (height/2 + area) - (height/2 - area))/2)
            for x in range(width/2 - area, width/2 + area):
                if done:
                    break
                for y in range(height/2 - area, height/2 + area):
                    if pixels[x, y] < 240:
                        count_gray += 1
                        if count_gray > number_white:
                            done = True
                        # end if
                    # end if
                # end for
            # end for
            # if image have a gray center, save the image position
            if done:
                items.append((lt_obj.bbox[0], lt_obj.bbox[3]))
            # end if
        # end if
        else:
            return parse_figure(lt_obj, items)  # Recursive
        # end else
    # end for
# end def


def parse_item(layout, check_pos, items):

    x_distance = 20
    y_distance = 5
    for lt_obj in layout:
        if isinstance(lt_obj, LTTextLine):
            for check in check_pos:
                if abs(check[0] - lt_obj.bbox[0]) < x_distance and abs(check[1] - lt_obj.bbox[3]) < y_distance:
                    items.append(unidecode(lt_obj.get_text()).replace('\n', ''))
        else:
            return parse_item(lt_obj, check_pos, items)
        # end if
    # end for
# end def


def main():

    filename_w_ext = os.path.basename(sys.argv[1])
    filename, file_extension = os.path.splitext(filename_w_ext)

    # verify numbers of arguments
    if len(sys.argv) < 2:
        print 'Number of arguments invalid'
        sys.exit()
    # end if

    # verify if file exist
    if not os.path.isfile(sys.argv[1]):
        print 'File does not exist'
        sys.exit()
    # end if

    # verify if file is a pdf document
    if not file_extension == '.pdf':
        print 'File must have a .pdf extension'
        sys.exit()
    # end if

    start_time = time.time()
    # dictionary for storing all text {key = page, value = [(label_y_pos, label_text), associated text]}
    text = get_text_pdf(sys.argv[1])

    # write csv file
    write_csv(str(filename) + '.csv', text)

    text_time = time.time()
    print('text extraction time: %10.2f sec' % (text_time - start_time))

    # api annotation
    if api_key == '':
        print 'bio-ontology api key for api authorization not found. Set api key in python file'
        sys.exit()

    api_params = dict(
        apikey=api_key,
        format=api_format,
        ontologies=api_ontology
    )
    api_annotation(str(filename) + '-api_annotation.csv', sections, text, api_params)
    annotation_time = time.time()
    print('elapsed time: %10.2f sec' % (annotation_time - start_time))
# end def


if __name__ == '__main__':
    main()
