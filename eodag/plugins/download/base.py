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

import hashlib
import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from datetime import datetime, timedelta
from time import sleep
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from eodag.api.search_result import SearchResult
from eodag.plugins.base import PluginTopic
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    ProgressCallback,
    StreamResponse,
    deepcopy,
    sanitize,
    uri_to_path,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
)
from eodag.utils.notebook import NotebookWidgets

if TYPE_CHECKING:
    from requests.auth import AuthBase

    from eodag.api.core import EODataAccessGateway
    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import DownloadedCallback, Unpack


logger = logging.getLogger("eodag.download.base")

T = TypeVar("T")


class Download(PluginTopic):
    """Base Download Plugin.

    A Download plugin has two download methods that it must implement:

    - ``download``: download a single :class:`~eodag.api.product._product.EOProduct`
    - ``download_all``: download multiple products from a :class:`~eodag.api.search_result.SearchResult`

    They must:

    - download data in the ``outputs_prefix`` folder defined in the plugin's
      configuration or passed through kwargs
    - download data from all pages of the search of results given in parameters
      if ``exhaust`` is set to True (False by default) with ``download_all``
    - extract products from their archive (if relevant) if ``extract`` is set to True
      (True by default)
    - save a product in an archive/directory (in ``outputs_prefix``) whose name must be
      the product's ``title`` property
    - update the product's ``location`` attribute once its data is downloaded (and
      eventually after it's extracted) to the product's location given as a file URI
      (e.g. 'file:///tmp/product_folder' on Linux or
      'file:///C:/Users/username/AppData/LOcal/Temp' on Windows)
    - save a *record* file in the directory ``outputs_prefix/.downloaded`` whose name
      is built on the MD5 hash of the product's ``product_type`` and ``properties['id']``
      attributes (``hashlib.md5((product.product_type+"-"+product.properties['id']).encode("utf-8")).hexdigest()``)
      and whose content is the product's ``remote_location`` attribute itself.
    - not try to download a product whose ``location`` attribute already points to an
      existing file/directory
    - not try to download a product if its *record* file exists as long as the expected
      product's file/directory. If the *record* file only is found, it must be deleted
      (it certainly indicates that the download didn't complete)

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(Download, self).__init__(provider, config)
        self._authenticate = bool(getattr(self.config, "authenticate", False))

    def download(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        r"""
        Base download method. Not available, it must be defined for each plugin.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. '/tmp/product.zip' on Linux or
            'C:\\Users\\username\\AppData\\Local\\Temp\\product.zip' on Windows)
        :rtype: str
        """
        raise NotImplementedError(
            "A Download plugin must implement a method named download"
        )

    def _stream_download_dict(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> StreamResponse:
        r"""
        Base _stream_download_dict method. Not available, it must be defined for each plugin.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: Dictionnary of :class:`~fastapi.responses.StreamingResponse` keyword-arguments
        :rtype: dict
        """
        raise NotImplementedError(
            "Download streaming must be implemented using a method named _stream_download_dict"
        )

    def _prepare_download(
        self,
        product: EOProduct,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Check if file has already been downloaded, and prepare product download

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :returns: fs_path, record_filename
        :rtype: Tuple[Optional[str], Optional[str]]
        """
        if product.location != product.remote_location:
            fs_path = uri_to_path(product.location)
            # The fs path of a product is either a file (if 'extract' config is False) or a directory
            if os.path.isfile(fs_path) or os.path.isdir(fs_path):
                logger.info(
                    f"Product already present on this platform. Identifier: {fs_path}",
                )
                # Do not download data if we are on site. Instead give back the absolute path to the data
                return fs_path, None

        url = product.remote_location
        if not url:
            logger.debug(
                f"Unable to get download url for {product}, skipping download",
            )
            return None, None
        logger.info(
            f"Download url: {url}",
        )

        outputs_prefix = (
            kwargs.pop("outputs_prefix", None)
            or getattr(self.config, "outputs_prefix", tempfile.gettempdir())
            or tempfile.gettempdir()
        )
        outputs_extension = kwargs.get("outputs_extension", None) or getattr(
            self.config, "outputs_extension", ".zip"
        )

        # Strong asumption made here: all products downloaded will be zip files
        # If they are not, the '.zip' extension will be removed when they are downloaded and returned as is
        prefix = os.path.abspath(outputs_prefix)
        sanitized_title = sanitize(product.properties["title"])
        if sanitized_title == product.properties["title"]:
            collision_avoidance_suffix = ""
        else:
            collision_avoidance_suffix = "-" + sanitize(product.properties["id"])
        fs_path = os.path.join(
            prefix,
            f"{sanitize(product.properties['title'])}{collision_avoidance_suffix}{outputs_extension}",
        )
        fs_dir_path = (
            fs_path.replace(outputs_extension, "") if outputs_extension else fs_path
        )
        download_records_dir = os.path.join(prefix, ".downloaded")
        try:
            os.makedirs(download_records_dir)
        except OSError as exc:
            import errno

            if exc.errno != errno.EEXIST:  # Skip error if dir exists
                import traceback as tb

                logger.warning(
                    f"Unable to create records directory. Got:\n{tb.format_exc()}",
                )
        record_filename = os.path.join(
            download_records_dir, self.generate_record_hash(product)
        )
        if os.path.isfile(record_filename) and os.path.isfile(fs_path):
            logger.info(
                f"Product already downloaded: {fs_path}",
            )
            return (
                self._finalize(fs_path, progress_callback=progress_callback, **kwargs),
                None,
            )
        elif os.path.isfile(record_filename) and os.path.isdir(fs_dir_path):
            logger.info(
                f"Product already downloaded: {fs_dir_path}",
            )
            return (
                self._finalize(
                    fs_dir_path, progress_callback=progress_callback, **kwargs
                ),
                None,
            )
        # Remove the record file if fs_path is absent (e.g. it was deleted while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug(
                f"Record file found ({record_filename}) but not the actual file",
            )
            logger.debug(
                f"Removing record file : {record_filename}",
            )
            os.remove(record_filename)

        return fs_path, record_filename

    def generate_record_hash(self, product: EOProduct) -> str:
        """Generate the record hash of the given product.

        The MD5 hash is built from the product's ``product_type`` and ``properties['id']`` attributes
        (``hashlib.md5((product.product_type+"-"+product.properties['id']).encode("utf-8")).hexdigest()``)

        :param product: The product to calculate the record hash
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :returns: The MD5 hash
        :rtype: str
        """
        # In some unit tests, `product.product_type` is `None` and `product.properties["id"]` is `ìnt`
        product_hash = str(product.product_type) + "-" + str(product.properties["id"])
        return hashlib.md5(product_hash.encode("utf-8")).hexdigest()

    def _resolve_archive_depth(self, product_path: str) -> str:
        """Update product_path using archive_depth from provider configuration.

        Handle depth levels in the product archive. For example, if the downloaded archive was
        extracted to: ``/top_level/product_base_dir`` and ``archive_depth`` was configured to 2, the product
        location will be ``/top_level/product_base_dir``.
        WARNING: A strong assumption is made here: there is only one subdirectory per level

        :param product_path: The path to the extracted product
        :type product_path: str
        :returns: The path to the extracted product with the right depth
        :rtype: str
        """
        archive_depth = getattr(self.config, "archive_depth", 1)
        count = 1
        while count < archive_depth:
            product_path = os.path.join(product_path, os.listdir(product_path)[0])
            count += 1
        return product_path

    def _finalize(
        self,
        fs_path: str,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> str:
        """Finalize the download process.

        :param fs_path: The path to the local zip archive downloaded or already present
        :type fs_path: str
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :returns: The absolute path to the product
        :rtype: str
        """
        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback(
                unit="file",
                unit_scale=False,
                position=2,
            )
            # one shot progress callback to close after download
            close_progress_callback = True
        else:
            close_progress_callback = False
            progress_callback.unit = "file"
            progress_callback.unit_scale = False
            progress_callback.refresh()

        extract = kwargs.pop("extract", None)
        extract = (
            extract if extract is not None else getattr(self.config, "extract", True)
        )
        if not extract:
            logger.info("Extraction not activated. The product is available as is.")
            progress_callback(1, total=1)
            return fs_path

        delete_archive = kwargs.pop("delete_archive", None)
        delete_archive = (
            delete_archive
            if delete_archive is not None
            else getattr(self.config, "delete_archive", True)
        )
        outputs_extension = kwargs.pop("outputs_extension", ".zip")

        product_path = (
            fs_path[: fs_path.index(outputs_extension)]
            if outputs_extension in fs_path
            else fs_path
        )
        product_path_exists = os.path.exists(product_path)
        if product_path_exists and os.path.isfile(product_path):
            logger.info(
                f"Remove existing partially downloaded file: {product_path}"
                f" ({os.stat(product_path).st_size}/{os.stat(fs_path).st_size})"
            )
            os.remove(product_path)
        elif (
            product_path_exists
            and os.path.isdir(product_path)
            and len(os.listdir(product_path)) == 0
        ):
            logger.info(f"Remove existing empty destination directory: {product_path}")
            os.rmdir(product_path)
        elif (
            product_path_exists
            and os.path.isdir(product_path)
            and len(os.listdir(product_path)) > 0
        ):
            logger.info(
                f"Extraction cancelled, destination directory already exists and is not empty: {product_path}"
            )
            progress_callback(1, total=1)
            return product_path
        outputs_prefix = (
            kwargs.pop("outputs_prefix", None) or self.config.outputs_prefix
        )

        if not os.path.exists(product_path):
            logger.info("Extraction activated")
            progress_callback.desc = (
                f"Extracting files from {os.path.basename(fs_path)}"
            )
            progress_callback.refresh()

            outputs_dir = os.path.join(outputs_prefix, product_path)
            tmp_dir = tempfile.TemporaryDirectory()
            extraction_dir = os.path.join(tmp_dir.name, os.path.basename(outputs_dir))

            if fs_path.endswith(".zip"):
                with zipfile.ZipFile(fs_path, "r") as zfile:
                    fileinfos = zfile.infolist()

                    progress_callback.reset(total=len(fileinfos))

                    for fileinfo in fileinfos:
                        zfile.extract(
                            fileinfo,
                            path=extraction_dir,
                        )
                        progress_callback(1)
                # in some cases, only a lone file is extracted without being in a directory
                # then, we create a directory in which we place this file
                product_extraction_path = self._resolve_archive_depth(extraction_dir)
                if os.path.isfile(product_extraction_path) and not os.path.isdir(
                    outputs_dir
                ):
                    os.makedirs(outputs_dir)
                shutil.move(product_extraction_path, outputs_dir)

            elif fs_path.endswith(".tar") or fs_path.endswith(".tar.gz"):
                with tarfile.open(fs_path, "r") as zfile:
                    progress_callback.reset(total=1)
                    zfile.extractall(path=extraction_dir)
                    progress_callback(1)
                # in some cases, only a lone file is extracted without being in a directory
                # then, we create a directory in which we place this file
                product_extraction_path = self._resolve_archive_depth(extraction_dir)
                if os.path.isfile(product_extraction_path) and not os.path.isdir(
                    outputs_dir
                ):
                    os.makedirs(outputs_dir)
                shutil.move(product_extraction_path, outputs_dir)
            else:
                progress_callback(1, total=1)

            tmp_dir.cleanup()

            if delete_archive:
                logger.info(f"Deleting archive {os.path.basename(fs_path)}")
                os.unlink(fs_path)
            else:
                logger.info(
                    f"Archive deletion is deactivated, keeping {os.path.basename(fs_path)}"
                )
        else:
            progress_callback(1, total=1)

        # close progress bar if needed
        if close_progress_callback:
            progress_callback.close()

        return product_path

    def download_all(
        self,
        products: SearchResult,
        dag: EODataAccessGateway,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> List[str]:
        """
        Base download_all method.

        This specific implementation uses the :meth:`eodag.plugins.download.base.Download.download` method
        implemented by the plugin to **sequentially** attempt to download products.

        :param products: Products to download
        :type products: :class:`~eodag.api.search_result.SearchResult`
        :param dag: The gateway to download products
        :type dag: :class:`~eodag.api.core.EODataAccessGateway`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param downloaded_callback: (optional) A method or a callable object which takes
                                    as parameter the ``product``. You can use the base class
                                    :class:`~eodag.api.product.DownloadedCallback` and override
                                    its ``__call__`` method. Will be called each time a product
                                    finishes downloading
        :type downloaded_callback: Callable[[:class:`~eodag.api.product._product.EOProduct`], None]
                                   or None
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool),
                        `dl_url_params` (dict) and `exhaust` (bool) can be provided as
                        additional kwargs and will override any other values defined in a
                        configuration file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: List of absolute paths to the downloaded products in the local
            filesystem (e.g. ``['/tmp/product.zip']`` on Linux or
            ``['C:\\Users\\username\\AppData\\Local\\Temp\\product.zip']`` on Windows)
        :rtype: list
        """
        if kwargs.pop("exhaust", False):
            logger.info(
                (
                    "Searching other products from all pages of the same search request "
                    "as the one used for these products to download all of them"
                )
            )
            # record search kwargs of products in the dag to skip their search page during the new search with all pages
            search_kwargs = dag.search_kwargs_for_exhaust = products.search_kwargs
            if search_kwargs:
                other_products = SearchResult([])
                tmp_search_kwargs = deepcopy(search_kwargs)
                # remove "page" parameter which is not used in the following search method
                del tmp_search_kwargs["page"]
                # search products from all pages of the same search request than the one of the previous products
                # the provider must be the one with which products were found
                for page_results in dag.search_iter_page(
                    items_per_page=tmp_search_kwargs.pop("items_per_page", None),
                    start=tmp_search_kwargs.pop("startTimeFromAscendingNode", None),
                    end=tmp_search_kwargs.pop("completionTimeFromAscendingNode", None),
                    geom=tmp_search_kwargs.pop("geometry", None),
                    locations=tmp_search_kwargs.pop("locations", None),
                    provider=products[0].provider,
                    **tmp_search_kwargs,
                ):
                    other_products.data.extend(page_results.data)
                # the dag does not need search kwargs record anymore
                dag.search_kwargs_for_exhaust = None
                logger.info(f"Found {len(other_products)} other result(s)")
                if other_products:
                    # apply on the new results the same cruncher(s) as the one(s) used to filter initial results
                    for i, cruncher in enumerate(products.crunchers):
                        if i == 0:
                            logger.info("Apply the crunchers used on initial results")
                        other_products = other_products.crunch(
                            cruncher, **search_kwargs
                        )
                    # add the new results to the initial ones
                    products.data.extend(other_products.data)
            else:
                logger.info(
                    "Products from all pages have already been searched, then the 'exhaust' parameter is not used here"
                )
            logger.info(f"Downloading {len(products)} products")
        # Products are going to be removed one by one from this sequence once
        # downloaded.
        products = products[:]
        paths: List[str] = []
        # initiate retry loop
        start_time = datetime.now()
        stop_time = start_time + timedelta(minutes=timeout)
        nb_products = len(products)
        retry_count = 0
        # another output for notbooks
        nb_info = NotebookWidgets()

        for product in products:
            product.next_try = start_time

        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback(
                total=nb_products,
                unit="product",
                desc="Downloaded products",
                unit_scale=False,
            )
            product_progress_callback = None
        else:
            product_progress_callback = progress_callback.copy()
            progress_callback.reset(total=nb_products)
            progress_callback.unit = "product"
            progress_callback.desc = "Downloaded products"
            progress_callback.unit_scale = False
        progress_callback.refresh()

        with progress_callback as bar:
            while "Loop until all products are download or timeout is reached":
                # try downloading each product before retry
                for idx, product in enumerate(products):
                    if datetime.now() >= product.next_try:
                        products[idx].next_try += timedelta(minutes=wait)
                        try:
                            paths.append(
                                product.download(
                                    progress_callback=product_progress_callback,
                                    wait=wait,
                                    timeout=-1,
                                    **kwargs,
                                )
                            )

                            if downloaded_callback:
                                downloaded_callback(product)

                            # product downloaded, to not retry it
                            products.remove(product)
                            bar(1)

                            # reset stop time for next product
                            stop_time = datetime.now() + timedelta(minutes=timeout)

                        except NotAvailableError as e:
                            logger.info(e)
                            continue

                        except (AuthenticationError, MisconfiguredError):
                            logger.exception(
                                f"Stopped because of credentials problems with provider {self.provider}"
                            )
                            raise

                        except RuntimeError:
                            import traceback as tb

                            logger.error(
                                f"A problem occurred during download of product: {product}. "
                                "Skipping it"
                            )
                            logger.debug(f"\n{tb.format_exc()}")
                            stop_time = datetime.now()

                        except Exception:
                            import traceback as tb

                            logger.warning(
                                f"A problem occurred during download of product: {product}. "
                                "Skipping it",
                            )
                            logger.debug(f"\n{tb.format_exc()}")

                if (
                    len(products) > 0
                    and datetime.now() < products[0].next_try
                    and datetime.now() < stop_time
                ):
                    wait_seconds = (products[0].next_try - datetime.now()).seconds
                    retry_count += 1
                    info_message = (
                        f"[Retry #{retry_count}, {nb_products - len(products)}/{nb_products} D/L] "
                        f"Waiting {wait_seconds}s until next download try (retry every {wait}' for {timeout}')"
                    )
                    logger.info(info_message)
                    nb_info.display_html(info_message)
                    sleep(wait_seconds + 1)
                elif len(products) > 0 and datetime.now() >= stop_time:
                    logger.warning(
                        f"{len(products)} products could not be downloaded: "
                        + str([prod.properties["title"] for prod in products])
                    )
                    break
                elif len(products) == 0:
                    break

        return paths

    def _download_retry(
        self, product: EOProduct, wait: int, timeout: int
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Download retry decorator.

        Retries the wrapped  download method after `wait` minutes if a NotAvailableError
        exception is thrown until `timeout` minutes.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param wait: If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :returns: decorator
        :rtype: Callable[[Callable[..., T]], Callable[..., T]]
        """

        def decorator(download: Callable[..., T]) -> Callable[..., T]:
            def download_and_retry(*args: Any, **kwargs: Unpack[DownloadConf]) -> T:
                # initiate retry loop
                start_time = datetime.now()
                stop_time = start_time + timedelta(minutes=timeout)
                product.next_try = start_time
                retry_count = 0
                not_available_info = "The product could not be downloaded"
                # another output for notebooks
                nb_info = NotebookWidgets()

                while "Loop until products download succeeds or timeout is reached":
                    datetime_now = datetime.now()

                    if datetime_now >= product.next_try:
                        product.next_try += timedelta(minutes=wait)
                        try:
                            return download(*args, **kwargs)

                        except NotAvailableError as e:
                            if not getattr(self.config, "order_enabled", False):
                                raise NotAvailableError(
                                    f"Product is not available for download and order is not supported for"
                                    f" {self.provider}, {e}"
                                )
                            not_available_info = str(e)

                    if datetime_now >= product.next_try and datetime_now < stop_time:
                        wait_seconds: Union[float, int] = (
                            datetime_now - product.next_try + timedelta(minutes=wait)
                        ).seconds
                        retry_count += 1
                        retry_info = (
                            f"[Retry #{retry_count}] Waited {wait_seconds}s, trying again to download ordered product"
                            f" (retry every {wait}' for {timeout}')"
                        )
                        logger.info(not_available_info)
                        # Retry-After info from Response header
                        if hasattr(self, "stream"):
                            retry_server_info = self.stream.headers.get(
                                "Retry-After", ""
                            )
                            if retry_server_info:
                                logger.debug(
                                    f"[{self.provider} response] Retry-After: {retry_server_info}"
                                )
                        logger.debug(retry_info)
                        nb_info.display_html(retry_info)
                        product.next_try = datetime_now
                    elif datetime_now < product.next_try and datetime_now < stop_time:
                        wait_seconds = (product.next_try - datetime_now).seconds + (
                            product.next_try - datetime_now
                        ).microseconds / 1e6
                        retry_count += 1
                        retry_info = (
                            f"[Retry #{retry_count}] Waiting {wait_seconds}s until next download try"
                            f" for ordered product (retry every {wait}' for {timeout}')"
                        )
                        logger.info(not_available_info)
                        # Retry-After info from Response header
                        if hasattr(self, "stream"):
                            retry_server_info = self.stream.headers.get(
                                "Retry-After", ""
                            )
                            if retry_server_info:
                                logger.debug(
                                    f"[{self.provider} response] Retry-After: {retry_server_info}"
                                )
                        logger.debug(retry_info)
                        nb_info.display_html(retry_info)
                        sleep(wait_seconds)
                    elif datetime_now >= stop_time and timeout > 0:
                        if "storageStatus" not in product.properties:
                            product.properties["storageStatus"] = "N/A status"
                        logger.info(not_available_info)
                        raise NotAvailableError(
                            f"{product.properties['title']} is not available ({product.properties['storageStatus']})"
                            f" and could not be downloaded, timeout reached"
                        )
                    elif datetime_now >= stop_time:
                        raise NotAvailableError(not_available_info)

                return download(*args, **kwargs)

            return download_and_retry

        return decorator
