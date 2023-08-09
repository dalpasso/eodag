# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging
from collections import UserList
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from shapely.geometry import GeometryCollection, shape

from eodag.api.product import EOProduct
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.crunch.filter_property import FilterProperty

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.plugins.crunch.base import Crunch

logger = logging.getLogger("eodag.search_result")


class SearchResult(UserList):
    """An object representing a collection of :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :type products: list(:class:`~eodag.api.product._product.EOProduct`)
    :param number_matched: (optional) the estimated total number of matching results
    :type number_matched: Optional[int]
    :ivar search_kwargs: The search kwargs used by eodag to search for the product
    :vartype search_kwargs: Any
    :ivar crunchers: The list of crunchers used to filter these products
    :vartype crunchers: list(tuple(subclass of :class:`~eodag.plugins.crunch.base.Crunch`, dict))
    """

    data: List[EOProduct]

    def __init__(
        self, products: List[EOProduct], number_matched: Optional[int] = None
    ) -> None:
        super(SearchResult, self).__init__(products)
        self.number_matched = number_matched
        self.search_kwargs = None
        self.crunchers = []

    def crunch(self, cruncher: Crunch, **search_params: Any) -> SearchResult:
        """Do some crunching with the underlying EO products.

        :param cruncher: The plugin instance to use to work on the products
        :type cruncher: subclass of :class:`~eodag.plugins.crunch.base.Crunch`
        :param search_params: The criteria that have been used to produce this result
        :type search_params: dict
        :returns: The result of the application of the crunching method to the EO products
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        for results_cruncher in self.crunchers:
            if (
                cruncher.__class__.__name__ == results_cruncher.__class__.__name__
                and cruncher.config == results_cruncher.config
            ):
                logger.info(
                    (
                        f"The cruncher '{cruncher.__class__.__name__}' has already been used "
                        "for these search results with the following parameter(s): "
                        f"{cruncher.config}. Please change parameters or use an other cruncher"
                    )
                )
                return self
        crunched_results_list = cruncher.proceed(self.data, **search_params)
        crunched_results = SearchResult(crunched_results_list)
        crunched_results.search_kwargs = self.search_kwargs
        self.crunchers.append(cruncher)
        crunched_results.crunchers = self.crunchers
        return crunched_results

    def filter_date(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_date.FilterDate` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterDate(dict(start=start, end=end)))

    def filter_latest_intersect(
        self, geometry: Union[Dict[str, Any], BaseGeometry, Any]
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestIntersect({}), geometry=geometry)

    def filter_latest_by_name(self, name_pattern: str) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestByName(dict(name_pattern=name_pattern)))

    def filter_overlap(
        self,
        geometry: Any,
        minimum_overlap: int = 0,
        contains: bool = False,
        intersects: bool = False,
        within: bool = False,
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_overlap.FilterOverlap` crunch,
        check its documentation to know more.
        """
        return self.crunch(
            FilterOverlap(
                dict(
                    minimum_overlap=minimum_overlap,
                    contains=contains,
                    intersects=intersects,
                    within=within,
                )
            ),
            geometry=geometry,
        )

    def filter_property(
        self, operator: str = "eq", **search_property: Any
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_property.FilterProperty` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterProperty(dict(operator=operator, **search_property)))

    def filter_online(self) -> SearchResult:
        """
        Use cruncher :class:`~eodag.plugins.crunch.filter_property.FilterProperty`,
        filter for online products.
        """
        return self.filter_property(storageStatus="ONLINE")

    @staticmethod
    def from_geojson(feature_collection: Dict[str, Any]) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :type feature_collection: dict
        :returns: An eodag representation of a search result
        :rtype: :class:`~eodag.api.search_result.SearchResult`
        """
        return SearchResult(
            [
                EOProduct.from_geojson(feature)
                for feature in feature_collection["features"]
            ]
        )

    def as_geojson_object(self) -> Dict[str, Any]:
        """GeoJSON representation of SearchResult"""
        return {
            "type": "FeatureCollection",
            "features": [product.as_dict() for product in self],
        }

    def as_shapely_geometry_object(self) -> GeometryCollection:
        """:class:`shapely.geometry.GeometryCollection` representation of SearchResult"""
        return GeometryCollection(
            [
                shape(feature["geometry"]).buffer(0)
                for feature in self.as_geojson_object()["features"]
            ]
        )

    def as_wkt_object(self) -> str:
        """WKT representation of SearchResult"""
        return self.as_shapely_geometry_object().wkt

    @property
    def __geo_interface__(self) -> Dict[str, Any]:
        """Implements the geo-interface protocol.

        See https://gist.github.com/sgillies/2217756
        """
        return self.as_geojson_object()

    def _repr_html_(self):
        total_count = f"/{self.number_matched}" if self.number_matched else ""
        return (
            f"""<table>
                <thead><tr><td style='text-align: left; color: grey;'>
                 {type(self).__name__}&ensp;({len(self)}{total_count})
                </td></tr></thead>
            """
            + "".join(
                [
                    f"""<tr><td style='text-align: left;'>
                <details><summary style='color: grey; font-family: monospace;'>
                    {i}&ensp;
                    {type(p).__name__}(id=<span style='color: black;'>{
                        p.properties['id']
                    }</span>, provider={p.provider})
                </summary>
                {p._repr_html_()}
                </details>
                </td></tr>
                """
                    for i, p in enumerate(self)
                ]
            )
            + "</table>"
        )


class RawSearchResult(UserList):
    """An object representing a collection of raw/unparsed search results obtained from a provider.

    :param results: A list of raw/unparsed search results
    :type results: List[Any]
    """

    data: List[Any]
    query_params: Dict[str, Any]
    product_type_def_params: Dict[str, Any]

    def __init__(self, results: List[Any]) -> None:
        super(RawSearchResult, self).__init__(results)
