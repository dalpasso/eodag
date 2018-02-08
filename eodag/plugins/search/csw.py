# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging
import uuid
from urllib.parse import urlparse

from owslib.csw import CatalogueServiceWeb
from owslib.fes import (
    BBox, PropertyIsEqualTo, PropertyIsGreaterThanOrEqualTo, PropertyIsLessThanOrEqualTo, PropertyIsLike,
)

from eodag.api.product import EOProduct
from eodag.plugins.search.base import Search
from eodag.utils.import_system import patch_owslib_requests


logger = logging.getLogger('eodag.plugins.search.csw')

# Configuration keys
SEARCH_DEF = 'search_definitions'
PRODUCT_TYPE = 'pt_tags'
MATCHING = 'matching'
DATE = 'date_tags'


class CSWSearch(Search):

    def __init__(self, config):
        super(CSWSearch, self).__init__(config)
        self.catalog = None

    def query(self, product_type, **kwargs):
        logger.info('New search for product type : %s on %s interface', product_type, self.name)
        auth = kwargs.pop('auth', None)
        if auth is not None:
            self.__init_catalog(**auth.config['credentials'])
        else:
            self.__init_catalog()
        results = []

        def build_product(rec):
            """Enable search results to be handled by http download plugin"""
            eop = EOProduct(rec)
            for ref in eop.original_repr.references:
                if 'WWW:DOWNLOAD' in ref['scheme'] and 'http--download' in ref['scheme']:
                    # TODO: remove this dirty hack specific to geostorm-ce hostname
                    parsed_ref_url = urlparse(ref['url'])
                    parsed_config_url = urlparse(self.config['api_endpoint'])
                    if parsed_ref_url.netloc != parsed_config_url.netloc:
                        eop.location_url_tpl = '{}://{}{}{}{}'.format(
                            parsed_ref_url.scheme, parsed_config_url.netloc, ':'.join(parsed_ref_url.port or ''),
                            parsed_ref_url.path, parsed_ref_url.query
                        )
                    else:
                        eop.location_url_tpl = ref['url']
                    eop.local_filename = rec.identifier.replace(':', '_').replace('-', '_')
                    break
            return eop
        for product_type_search_tag in self.config[SEARCH_DEF][PRODUCT_TYPE]:
            constraints = self.__convert_query_params(product_type_search_tag, product_type, kwargs)
            with patch_owslib_requests(verify=False):
                logger.debug('Querying %s for product type %s', product_type_search_tag, product_type)
                self.catalog.getrecords2(constraints=constraints, esn='full', maxrecords=10)
            results.extend(build_product(record) for record in self.catalog.records.values())
        logger.info('Found %s results', len(results))
        return results

    def __init_catalog(self, username=None, password=None):
        """Initializes a catalogue by performing a GetCapabilities request on the url"""
        if not self.catalog:
            logger.debug('Initialising CSW catalog at %s', self.config['api_endpoint'])
            with patch_owslib_requests(verify=False):
                self.catalog = CatalogueServiceWeb(
                    self.config['api_endpoint'],
                    version=self.config.get('version', '2.0.2'),
                    username=username,
                    password=password
                )

    def __convert_query_params(self, pt_tag, product_type, params):
        """Translates eodag search to CSW constraints using owslib constraint classes"""
        constraints = []
        # How the match should be performed (fuzzy, prefix or postfix). defaults to fuzzy
        matching = self.config[SEARCH_DEF][MATCHING].get(
            pt_tag,
            self.config[SEARCH_DEF][MATCHING].get('*', 'fuzzy')
        )
        if matching == 'prefix':
            constraints.append(PropertyIsLike(pt_tag, '{}%'.format(product_type)))
        elif matching == 'postfix':
            constraints.append(PropertyIsLike(pt_tag, '%{}'.format(product_type)))
        elif matching == 'exact':
            constraints.append(PropertyIsEqualTo(pt_tag, product_type))
        else:  # unknown matching is considered to be equal to 'fuzzy'
            constraints.append(PropertyIsLike(pt_tag, '%{}%'.format(product_type)))

        # footprint
        fp = params.get('footprints')
        if fp:
            constraints.append(BBox([fp['lonmin'], fp['latmin'], fp['lonmax'], fp['latmax']]))

        # dates
        start, end = params.get('startDate'), params.get('endDate')
        if start:
            constraints.append(PropertyIsGreaterThanOrEqualTo(self.config[SEARCH_DEF][DATE]['start'], start))
        if end:
            constraints.append(PropertyIsLessThanOrEqualTo(self.config[SEARCH_DEF][DATE]['end'], end))
        return [constraints] if len(constraints) > 1 else constraints
