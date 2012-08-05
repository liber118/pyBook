#!/usr/bin/env python
# encoding: utf-8

from lxml import etree
from subprocess import call
import cgi
import errno
import lxml.html
import os
import os.path
import shutil
import sys


######################################################################
## global definitions

uuid = None
title = None
author = None

uri_list = []
toc_xhtml = "toc.xhtml"

mimetype = {
    "png": "image/png",
    "jpg": "image/jpeg"
    }

ns = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'opf': 'http://www.idpf.org/2007/opf'
    }


######################################################################
## file utilities


def mkdir_p (path):
    """
    'mkdir -p' functionality, avoiding race condition
    """

    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise


######################################################################
## class definitions

class URI:
    """
    representation for an XHTML page
    """

    def __init__ (self, kind, id, label, img=None, guide=None):
        """
        initialize
        """

        self.kind = kind
        self.id = id
        self.label = label
        self.img = img
        self.guide = guide
        self.idref = "%s-%s" % (kind, id)
        self.uri = self.idref + ".xhtml"


    def gen_nav_point (self, xml, play_order):
        """
        generate an NCX <navPoint/> element, except for the closing tag
        """

        xml.append("<navPoint id=\"navpoint-%d\" playOrder=\"%d\">" % (play_order, play_order))
        xml.append("<navLabel><text>%s</text></navLabel>" % self.label)
        xml.append('<content src="%s"/>' % self.uri)


    def gen_opf_item (self, xml):
        """
        generate an OPF <item/> element
        """

        global mimetype
        
        xml.append('<item id="%s" href="%s" media-type="application/xhtml+xml"/>' % (self.idref, self.uri))

        if self.img:
            mime = mimetype[self.img.split(".")[-1]]
            xml.append('<item id="img-%s" href="img/%s" media-type="%s"/>' % (self.id, self.img, mime))


    def gen_opf_itemref (self, xml, linear):
        """
        generate an OPF <itemref/> element
        """

        yes_no = "no"

        if linear:
            yes_no = "yes"

        xml.append('<itemref idref="%s" linear="%s"/>' % (self.idref, yes_no))


    def format_content(self, epub_path, src_path):
        """
        copy/format an XHTML file
        """

        global uuid, title, author

        try:
            file_html = src_path + self.uri
            html = lxml.html.parse(file_html)

            xhtml = lxml.html.tostring(html, pretty_print=False, include_meta_content_type=False, encoding=None, method='xml')
            xml_str = "".join(xhtml.split("\n")[1:])

            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.XML(xml_str, parser=parser)

            for content in tree.xpath("/html/body/div"):
                xhtml = etree.tostring(content, method="xml", pretty_print=False)[5:-6]

            with open(epub_path + self.uri, "w") as f:
                label = cgi.escape(self.label).encode("ascii", "xmlcharrefreplace")

                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n')
                f.write('<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head>')
                f.write('<title>%s | %s</title>' % (label, title))
                f.write('<link rel="stylesheet" href="epub.css" type="text/css"/>')
                f.write('<meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8"/>')
                f.write('<meta name="EPB-UUID" content="%s"/>' % uuid)
                f.write('</head><body><div class="body" style="white-space:pre-wrap">')
                f.write(xhtml)
                f.write('</div></body></html>')

        except:
            sys.stderr.write("%(err)s\n%(data)s\n" % {"err": str(sys.exc_info()[0]), "data": file_html})
            raise


######################################################################
## XML formatters

def prep_ncx (tree):
    """
    prepare XML content for the NCX, with the side-effect of populating 'uri_list'
    http://www.niso.org/workrooms/daisy/Z39-86-2005.html#NCXElem
    """

    global uri_list, ns, uuid, title, author

    xml = []
    xml.append('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">')

    uuid = tree.xpath('/book/metadata/dc:identifier', namespaces=ns)[0].text
    title = tree.xpath('/book/metadata/dc:title', namespaces=ns)[0].text
    author = tree.xpath('/book/metadata/dc:creator', namespaces=ns)[0].text

    xml.append('<head>')
    xml.append('<meta name="dtb:uid" content="%s"/>' % uuid)
    xml.append('<meta name="epub-creator" content="Muted Horn v0.23"/>')
    xml.append('<!-- mortuus litteras buxum -->')
    xml.append('<meta name="dtb:depth" content="2"/>')
    xml.append('<meta name="dtb:totalPageCount" content="0"/>')
    xml.append('<meta name="dtb:maxPageNumber" content="0"/>')
    xml.append('</head>')

    xml.append('<docTitle><text>%s</text></docTitle>' % title)
    xml.append('<docAuthor><text>%s</text></docAuthor>' % author)
  
    play_order = 1
    xml.append('<navMap>')

    for page in tree.xpath("/book/front/page"):
        uri = URI("misc", page.get("id"), page.text.strip(), guide=page.get("guide"))
        uri.gen_nav_point(xml, play_order)
        uri_list.append(uri)
        play_order += 1
        xml.append('</navPoint>')

    for part in tree.xpath("/book/part"):
        uri = URI("part", part.get("id"), part.text.strip())
        uri.gen_nav_point(xml, play_order)
        uri_list.append(uri)
        play_order += 1

        for chapter in part.iter("chapter"):
            uri = URI("chapter", chapter.get("id"), chapter.text.strip(), img=chapter.get("img"))
            uri.gen_nav_point(xml, play_order)
            uri_list.append(uri)
            play_order += 1
            xml.append('</navPoint>')

        xml.append('</navPoint>')

    for page in tree.xpath("/book/back/page"):
        uri = URI("misc", page.get("id"), page.text.strip(), guide=page.get("guide"))
        uri.gen_nav_point(xml, play_order)
        uri_list.append(uri)
        play_order += 1
        xml.append('</navPoint>')

    xml.append('</navMap>')
    xml.append('</ncx>')

    return xml


def prep_opf (tree):
    """
    prepare XML content for the OPF (2.0.1 for Amazon Kindle)
    http://idpf.org/epub/20/spec/OPF_2.0.1_draft.htm
    """

    global uri_list, ns, toc_xhtml

    xml = []
    xml.append('<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">')

    for metadata in tree.xpath("/book/metadata"):
        xml.append(etree.tostring(metadata).strip())

    xml.append('<manifest>')
    xml.append('<item id="stylesheet" href="epub.css" media-type="text/css"/>')
    xml.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    xml.append('<item id="toc" href="%s" media-type="application/x-dtbncx+xml"/>' % toc_xhtml)

    for uri in uri_list:
        uri.gen_opf_item(xml)

    for img in tree.xpath("/book/assets/img"):
        src = img.get("src").split(".")
        id = src[0]
        mime = mimetype[src[-1]]
        xml.append('<item id="asset-%s" href="img/%s" media-type="%s"/>' % (id, img.get("src"), mime))

    xml.append('</manifest>')
    xml.append('<spine toc="ncx">')

    linear = False

    for uri in uri_list:
        uri.gen_opf_itemref(xml, linear)
        linear = True

    xml.append('</spine>')
    xml.append('<guide>')
    xml.append('<reference title="Table of Contents" type="toc" href="%s"/>' % toc_xhtml)

    for uri in uri_list:
        if uri.guide:
            xml.append('<reference title="%s" type="%s" href="%s"/>' % (uri.idref, uri.guide, uri.uri))

    xml.append('</guide>')
    xml.append('</package>')

    return xml


if __name__ == "__main__":
    # generate an EPUB
    # http://www.thebookdesigner.com/2009/09/parts-of-a-book/
    # http://www.hxa.name/articles/content/epub-guide_hxa7241_2007.html
    # http://www.ibm.com/developerworks/xml/tutorials/x-epubtut/index.html
    # http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf

    file_book = sys.argv[1]
    epub_path = sys.argv[2]
    src_path = sys.argv[3]

    try:
        tree = etree.parse(file_book)
    except:
        sys.stderr.write("%(err)s\n%(data)s\n" % {"err": str(sys.exc_info()[0]), "data": file_html})
        raise

    # write the "mimetype" (no trailing newline)
    
    with open(epub_path + "/mimetype", "w") as f:
        f.write('application/epub+zip')

    # write the "META-INF/container.xml"

    mkdir_p(epub_path + "META-INF")

    with open(epub_path + "META-INF/container.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')

    # write the "toc.ncx"

    xml = prep_ncx(tree)

    with open(epub_path + "toc.ncx", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n')
        f.write(etree.tostring(etree.fromstring("".join(xml)), pretty_print=True))

    # write the "content.opf"

    xml = prep_opf(tree)

    with open(epub_path + "content.opf", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(etree.tostring(etree.fromstring("".join(xml)), pretty_print=True))

    # copy the "epub.css" file

    shutil.copy2(src_path + "epub.css", epub_path)

    # copy the image files

    img_path = epub_path + "img"
    mkdir_p(img_path)

    for uri in uri_list:
        if uri.img:
            shutil.copy2(src_path + uri.img, img_path)

    for img in tree.xpath("/book/assets/img"):
        shutil.copy2(src_path + img.get("src"), img_path)

    # copy/format the XHTML files

    for uri in uri_list:
        uri.format_content(epub_path, src_path)

    # special case for TOC XHTML

    with open(epub_path + toc_xhtml, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n')
        f.write('<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head>')
        f.write('<title>Table of Contents | %s</title>' % title)
        f.write('<link rel="stylesheet" href="epub.css" type="text/css"/>')
        f.write('<meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8"/>')
        f.write('<meta name="EPB-UUID" content="%s"/>' % uuid)
        f.write('</head><body><div class="body" style="white-space:pre-wrap">')
        #f.write(xhtml)
        f.write('</div></body></html>')