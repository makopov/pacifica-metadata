#!/usr/bin/python
# -*- coding: utf-8 -*-
"""CherryPy DOI Registration Updater object class."""
from __future__ import print_function
from xml.etree import ElementTree
from cherrypy import tools, request, HTTPError
from dateutil.parser import parse
from pacifica.metadata.rest.doi_queries.doi_registration_base import DOIRegistrationBase
from pacifica.metadata.orm import DOIAuthors, DOIAuthorMapping, DOIEntries
from pacifica.metadata.orm.base import DB

# pylint: disable=too-few-public-methods


class DOIRegistrationUpdate(DOIRegistrationBase):
    """Updates the database with new DOI registration info from registration API."""

    exposed = True

    @staticmethod
    def _process_updated_osti_info(osti_xml_string):
        """Access the server at OSTI and get all the relevant details for this DOI."""
        try:
            tree = ElementTree.fromstring(osti_xml_string)
        except ElementTree.ParseError:
            raise HTTPError(400, 'Bad Request: Invalid XML Document')

        record = tree[0]
        current_status = record.attrib['status'].lower()
        release_status = record.attrib['released'].lower() == 'y'
        doi_string = record.find('doi').text

        doi_info, creators_block = DOIRegistrationUpdate._extract_doi_info_from_xml(
            record)

        if DOIRegistrationUpdate._check_for_doi_entry(doi_string):
            with DB.atomic():
                DOIRegistrationUpdate._extract_authors(
                    creators_block, doi_string)
                DOIRegistrationUpdate.change_doi_entry_info(
                    doi_string, doi_info, current_status, release_status)
        else:
            raise HTTPError(404, 'DOI Entry %s does not exist' % doi_string)

        return doi_string

    @staticmethod
    def _extract_doi_info_from_xml(record_object):
        doi_info = {}
        children = (child for child in record_object if child.text)
        creators_block = record_object.find('creatorsblock')
        record_object.remove(creators_block)
        for child in children:
            if 'date' in child.tag:
                info = parse(child.text).strftime('%Y-%m-%d')
            else:
                info = child.text
            doi_info[child.tag] = info
        return doi_info, creators_block

    @staticmethod
    def _check_for_doi_entry(doi_string):
        check_query = DOIEntries.select().where(DOIEntries.doi == doi_string)
        return check_query.count() > 0

    @staticmethod
    def _extract_authors(creatorsblock_element, doi_string):
        author_list = [{x.tag: x.text for x in el}
                       for el in creatorsblock_element]
        DOIRegistrationUpdate._update_author_info(author_list, doi_string)

    @staticmethod
    def _update_author_info(author_list, doi_string):
        # cross check author list with doi_authors
        # adding new and retrieving existing
        author_info_mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'affiliation_name': 'affiliation',
            'private_email': 'email',
            'orcid_id': 'orcid'
        }
        author_id_list = []
        for author_info in author_list:
            my_author_info = {}
            for key in author_info:
                my_key = author_info_mapping[key]
                my_author_info[my_key] = author_info[key]
            author, _created = DOIAuthors.get_or_create(**my_author_info)
            author_id_list.append(author.id)

        # add doi to author mappings
        author_order = 0
        for author_id in author_id_list:
            author_order += 1
            author_map_insert_item = {'author_order': author_order}
            author_map_lookup_item = {'author': author_id, 'doi': doi_string}
            DOIAuthorMapping.get_or_create(
                defaults=author_map_insert_item, **author_map_lookup_item)

    # CherryPy requires these named methods.
    # pylint: disable=invalid-name
    @staticmethod
    @tools.json_out()
    def POST():
        """Update existing DOI Entries."""
        valid_content_types = ['application/xml', 'text/xml']
        headers = request.headers
        if headers['Content-type'] not in valid_content_types:
            raise HTTPError(415, 'Expected an entity of content type %s' %
                            ', '.join(valid_content_types))

        osti_xml_string = request.body.read()
        doi_string = DOIRegistrationUpdate._process_updated_osti_info(
            osti_xml_string)

        return doi_string
