#!/usr/bin/python

from peewee import IntegerField, TextField, CharField
from metadata.orm import DB, PacificaModel

class Keywords(PacificaModel):
    keyword_id = IntegerField(default=-1, primary_key=True)
    product_id = IntegerField(default=-1)
    keyword = CharField(default="")
