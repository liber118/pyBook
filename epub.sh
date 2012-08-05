#!/bin/bash

DIR=EPUB
SRC=TBOO
TARGET=$SRC.epub

rm -rf $DIR
mkdir $DIR

./epub.py $SRC/EPUB.xml $DIR/ $SRC/

rm $TARGET
pushd $DIR
zip -X0 ../$TARGET mimetype
zip -Xur9D ../$TARGET *
popd

java -jar ~/opt/epubcheck-3.0b5/epubcheck-3.0b5.jar $TARGET

ls -lth $TARGET
