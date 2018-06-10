from pdfminer.pdfparser import PDFParser
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBoxHorizontal, LTChar, LTFigure, LTLine
from unidecode import unidecode
import sys
import os

horizontal_space = 210
vertical_offset = 5
write_csv = True


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


def is_valid_file(arg):
    if not os.path.exists(os.path.dirname(arg)):
        print ("The dir %s does not exist!" % os.path.dirname(arg))
        sys.exit()
    # end if


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

    # dictionary for storing all text {key = page, value = [(label_y_pos, label_text), associated text]}
    text = {}

    with PdfMinerWrapper(sys.argv[1]) as doc:

        last_page = 1
        last_label = 1

        # for each page in the document
        for page in doc:
            labels = []             # list for storing labels found

            # get labels
            # for each text box in page in x position lower than horizontal space
            for text_box in page:
                if text_box.bbox[0] < horizontal_space:
                    if not isinstance(text_box, LTTextBoxHorizontal):
                        continue
                    # end if
                    labels.append([(text_box.bbox[3], unidecode(text_box.get_text().replace('\n', ' ').replace(';', ' '))), ''])
                # end if
            # end for
            labels.append([(0, ''), ''])  # avoid overflow

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
                        text[last_page][last_label][1] += unidecode(text_box.get_text().replace('\n', ' '))
                        continue
                    # end if
                    found = False
                    # for each label in page
                    for i in xrange(0, len(labels) - 1):
                        # find associated label to text ( range between label and next label)
                        if labels[i][0][0] + vertical_offset > text_box.bbox[3] > labels[i + 1][0][0]:
                            labels[i][1] += ' ' + unidecode(text_box.get_text().replace('\n', ' '))
                            last_page = page.pageid
                            last_label = i
                            found = True
                            break
                        # end if
                    # end for

                    #
                    if not found and page.pageid > 1:
                        text[last_page][last_label][1] += unidecode(text_box.get_text().replace('\n', ' '))
                    # end if
                # end if
            # end for

            del labels[-1]
            text[page.pageid] = labels
        # end for

        write_csv(str(filename) + '.csv', text)
    # end with


if __name__ == '__main__':
    main()





