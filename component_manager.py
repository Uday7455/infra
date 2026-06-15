"""
Component Manager definitions
"""
from http.client import RemoteDisconnected
# pylint: disable=protected-access, too-many-locals
from typing import Callable, List, Tuple, Union
import pkgutil
import importlib
import inspect
import re
import time
import itertools
import logging
from selenium.common import exceptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from qali.intersight.gui import web_component
from qali.intersight.device_console_gui import web_component as dc_web_component
from qali.intersight.vcenter_plugin_gui import web_component as vc_web_component
from qali.intersight.gui import external
from qali.intersight.gui import util
from qali.intersight.gui.exceptions import UrlNotFound
from qali.intersight.gui.model_util import EXTERNAL_REPLACE_KEY
from qali.intersight.gui.model_util import CommonInfo
from qali.intersight.gui.model_util import ClickContextMap
from qali.intersight.gui.model_util import InputContextMap
from qali.intersight.gui.model_util import SelectContextMap
from qali.intersight.gui.model_util import NotificationContextMap
from qali.intersight.gui.model_util import DataContextMap
from qali.intersight.gui.model_util import ErrorContextMap
from qali.intersight.gui.model_util import TableContextMap
from qali.intersight.gui.model_util import CanvasContextMap
from qali.intersight.gui.model_util import Context
from qali.intersight.gui.model_util import ContextList
from qali.intersight.gui.model_util import CustomRemoteDisconnected
from qali.intersight.gui.web_component import WebComponent
from qali.intersight.gui.external import ExternalUIBase
from qali.intersight.gui.iframe_manager import IframeManager


# use try expect in case the library is being loaded in py2.
try:
    # python 3
    from urllib import parse
except ImportError:
    parse = None


class ComponentManager:
    """
        Component Manager class definition

        Component Manager is responsible to scan page and find web componenet in the page.

        It is also responsible to aggregate all the context from each web component.

        There is one component manager per Intersight UI object
    """

    HEX_REGEX = re.compile("[0-9a-fA-F]{4,}")

    WEB_COMPONENT_MAP = {}
    for submodule_info in pkgutil.iter_modules(web_component.__path__):
        submodule = importlib.import_module(
            "." + submodule_info[1], package="qali.intersight.gui.web_component")
        WEB_COMPONENT_MAP[submodule_info.name] = submodule.__dict__["".join(map(lambda x: x.title(),
                                                                                submodule_info.name.split("_")))]

    for submodule_info in pkgutil.iter_modules(dc_web_component.__path__):
        submodule = importlib.import_module(
            "." + submodule_info[1], package="qali.intersight.device_console_gui.web_component")
        WEB_COMPONENT_MAP[submodule_info.name] = submodule.__dict__["".join(map(lambda x: x.title(),
                                                                                submodule_info.name.split("_")))]
    # make it as a variable for Component manager initialisation
    for submodule_info in pkgutil.iter_modules(vc_web_component.__path__):
        submodule = importlib.import_module(
            "." + submodule_info[1], package="qali.intersight.vcenter_plugin_gui.web_component")
        WEB_COMPONENT_MAP[submodule_info.name] = submodule.__dict__["".join(map(lambda x: x.title(),
                                                                                submodule_info.name.split("_")))]

    EXTERNAL_MAP = {}
    for submodule_info in pkgutil.iter_modules(external.__path__):
        submodule = importlib.import_module(
            "." + submodule_info[1], package="qali.intersight.gui.external")
        for name, module_def in submodule.__dict__.items():
            if inspect.isclass(module_def) and hasattr(module_def, "NET_LOC") and hasattr(module_def, "TITLE"):
                for index in itertools.product(module_def.NET_LOC, module_def.TITLE):
                    EXTERNAL_MAP[index] = module_def

    def __init__(self,
                 driver: WebDriver,
                 url: str,
                 timeout: int,
                 iframe_manager: IframeManager,
                 notification_handler: Callable,
                 log: Callable,
                 screenshot: Callable) -> None:
        """
            init fucntion for component manager

            :param driver: seleniumn web driver
            :param url: url of the intersight gui.
            :param timeout: time to wait for url to be updated
            :param iframe_manager:  Iframe manager handler
            :param notification_handler:  callback for handling notfication 
            :param log: logging function
            :param screenshot: screenshot function
            :return: None

        """

        self.url = url
        parsed_url = parse.urlparse(url)
        netloc_reg = "[^/]*" + re.escape(".".join(parsed_url.netloc.split(".")[-2:]))
        self.url_host_re = re.compile(f"^{parsed_url.scheme}://{netloc_reg}")
        self.driver = driver

        self.web_components = None
        self._click_context = None
        self._input_context = None
        self._select_context = None
        self._table_context = None
        self._canvas_context = None
        self._data_context = None
        self._notification_context = None
        self._error_context = None

        self.timeout = timeout
        self.iframe_manager = iframe_manager
        self._notification_handler = notification_handler
        self.log = log
        self.screenshot = screenshot
        self.url_logged = None

    def find_components(self, common_info: CommonInfo) -> List[WebComponent]:
        """
            return web componets in a web page.

            :param common_info: common information shared between components.

            :return: list of web components in a page

        """

        rtr_list = []

        shadow_elements = util.get_body_shadow_host_elements(self.driver)

        try:
            iframe_replace, _, rtr_list = self.find_child_components(shadow_elements,
                                                                     [],
                                                                     [],
                                                                     common_info,
                                                                     [])
        except exceptions.StaleElementReferenceException:
            iframe_replace = False
        return iframe_replace, rtr_list

    def find_external_components(self, common_info: CommonInfo) -> List[ExternalUIBase]:
        """
            return component handler for external (i.e Non Intersight) page.

            :param common_info: common information shared between components.

            :return: component handler for external page

        """

        parsed_url = parse.urlparse(self.driver.current_url)
        net_loc = parsed_url.netloc

        title = self.driver.title
        net_loc = self.HEX_REGEX.sub(EXTERNAL_REPLACE_KEY, net_loc)
        title = self.HEX_REGEX.sub(EXTERNAL_REPLACE_KEY, title)

        for pattern_net_loc, pattern_title in self.EXTERNAL_MAP:
            if net_loc == pattern_net_loc and re.match(pattern_title, title):
                break
        else:
            common_info.log("unable to find page handler for {0} ({1}).  Current supported are {2}".format(
                (net_loc, title), self.driver.current_url, list(self.EXTERNAL_MAP)))
            return []
        return [self.EXTERNAL_MAP[(net_loc, pattern_title)](self.driver, common_info=common_info)]

    def find_child_components(self,
                              shadow_elements: List[WebElement],
                              css_paths: List[str],
                              context_paths: List[Union[Callable, str]],
                              common_info: CommonInfo,
                              ignore_replace_list: List[WebComponent]) -> Tuple[bool, List[WebComponent]]:
        """
            return web components of given shadow elements and thier children web components .

            :param shadow_elements: shadow elements for creating web components and their children web components
            :param css_paths: current css paths for the shadow elements
            :param context_paths: current context paths for the shadow elements
            :param common_info: common information shared between components.

            :return:  web components of given shadow elements and thier children web components and flag indicate
                      if the web components are replacing parent web components until terminating web component.

        """

        rtr_list = []
        child_list = []
        exclude_set = set()
        replaced = False
        iframe_replace = False

        debug = self.log(log_level=logging.DEBUG)

        for host_element in shadow_elements:
            if host_element is None:
                raise exceptions.NoSuchShadowRootException(f"host_element with css {css_paths}")
            if host_element.id not in exclude_set:
                # make sure host not in exlude set.
                # exclude set is updated by html leaf web component
                name = host_element.tag_name
                python_name = name.replace("-", "_")
                if python_name in self.WEB_COMPONENT_MAP:
                    if debug:
                        self.log("Processing web component {0}/{1}".format("/".join(css_paths),
                                                                           name),
                                 logging.DEBUG)

                    web_component_obj = self.WEB_COMPONENT_MAP[python_name](
                        self.driver, host_element, css_paths, context_paths, common_info=common_info)

                    if web_component_obj.ignore_replace:
                        ignore_replace_list.append(web_component_obj)
                    else:
                        rtr_list.append(web_component_obj)

                    if debug:
                        self.log("html_leaf = {0}, "
                                 "shadow_leaf = {1}, "
                                 "ignore_replace = {2}".format(web_component_obj.html_leaf,
                                                               web_component_obj.shadow_leaf,
                                                               web_component_obj.ignore_replace),
                                 logging.DEBUG)
                else:
                    if debug:
                        self.log("Processing undefined web component {0}/{1}".format("/".join(css_paths),
                                                                                     name),
                                 logging.DEBUG)

                    web_component_obj = WebComponent(
                        self.driver, host_element, css_paths, context_paths, common_info=common_info)
                    style = web_component_obj.web_element.get_attribute("style")
                    web_component_obj.shadow_leaf = ((style and "display: none" in style) or
                                                     web_component_obj.web_element.get_attribute("tabindex") == "-1")

                    web_component_obj.html_leaf = web_component_obj.shadow_leaf
                    if debug:
                        self.log("html_leaf = {0}, "
                                 "shadow_leaf = {1}".format(web_component_obj.html_leaf,
                                                            web_component_obj.shadow_leaf),
                                 logging.DEBUG)

                exclude_list = web_component_obj.exclude_child_web_component()
                if exclude_list:
                    if debug:
                        self.log("exclude list is {0}".format(exclude_list), logging.DEBUG)
                    exclude_set = exclude_set.union(exclude_list)

                iframe_element = web_component_obj.get_iframe()
                if iframe_element:
                    original_iframe = self.iframe_manager.iframes
                    iframes = self.iframe_manager.iframes + [iframe_element]
                    self.iframe_manager.iframes = iframes
                    try:
                        new_common_info = CommonInfo(
                            common_info.url, self, iframes, common_info.log)
                        iframe_replace, new_children_list = self.find_components(new_common_info)
                        if iframe_replace:
                            rtr_list = []
                            child_list = new_children_list
                            replaced = True
                            # the component list need to be replaced, so we can stop processing here
                            break
                        child_list += new_children_list

                    finally:
                        self.iframe_manager.iframes = original_iframe

                else:
                    if web_component_obj.path_contexts:
                        new_context_paths = context_paths + web_component_obj.path_contexts
                    else:
                        new_context_paths = context_paths
                    # handle web component with custom child components
                    child_components_info = web_component_obj.handle_child_components(
                        host_element)

                    if child_components_info.replace_require:
                        # remove all path context before, since they will get replaced
                        # ideally we should keep context till terminate replace element.
                        # but for now, remove everything to keep it simple
                        new_context_paths = []
                    final_new_child_list = []
                    for child_path_contexts, shadow_elems in child_components_info.component_info_list:
                        error = None
                        for backoff in util.wait_time.generator(0.01, 2, 10):
                            try:
                                iframe_replace, replaced, new_child_list = self.find_child_components(
                                    shadow_elems,
                                    css_paths +
                                    [name],
                                    new_context_paths + child_path_contexts,
                                    common_info,
                                    ignore_replace_list)
                                break
                            except RemoteDisconnected as remote_disconnected:
                                self.log("{} exception occurred in the processing of the component - \n {} "
                                         "with path {}".format(error, shadow_elems, css_paths + [name]))
                                error = remote_disconnected
                                time.sleep(backoff)
                        else:
                            raise CustomRemoteDisconnected(str(RemoteDisconnected)) from error

                        if replaced:
                            # the component list need to be replaced, so we can stop processing here
                            final_new_child_list = new_child_list
                            break
                        # add to final list
                        final_new_child_list.extend(new_child_list)
                    if child_components_info.replace_require or child_components_info.iframe_replace_require:
                        replaced = True
                        iframe_replace = child_components_info.iframe_replace_require
                        final_new_child_list = [web_component_obj] + final_new_child_list
                        if debug:
                            self.log("Replacement is required for component {0}".format(name), logging.DEBUG)
                    if not replaced:
                        child_list += final_new_child_list
                    else:
                        child_list = final_new_child_list

                    if replaced:
                        # component list replaced, so we do not need to process
                        # further for rest of the components
                        rtr_list = []
                        if web_component_obj and web_component_obj.terminate_replace:
                            if debug:
                                self.log("Replacement is terminated by component {0}".format(name), logging.DEBUG)
                            replaced = False
                        else:
                            break
        rtr_list.extend(child_list)
        rtr_list.extend(ignore_replace_list)
        return iframe_replace, replaced, rtr_list

    def print_components(self) -> None:
        """
            print shadow host element in a web page
        """
        for host_element in util.get_body_shadow_host_elements(self.driver):

            name = host_element.tag_name
            print(name)
            self.print_child_components(host_element, 2)

    def print_child_components(self,
                               element: WebElement,
                               spaces: int) -> None:
        """
            print children shadow host element of given web element.

            :param element: reference web element to get children shadow host element
            :param spaces: number of spaces to prefix the print.  This is to help to 
                           create a tree like printing
        """

        for host_element in util.get_child_shadow_host_elements(self.driver, element):
            name = host_element.tag_name
            print(" " * spaces + name)
            self.print_child_components(host_element, spaces + 2)

    def rescan_page(self) -> None:
        """
            rescane the web page.  This will essentially rescan the page and find all the 
            web component.  This is mainly trigger by each context manager.

            :return None        
        """

        error = None
        # set iframe to default
        self.iframe_manager.iframes = []
        curr_url = None
        for backoff in util.wait_time.generator(0.01, 1, self.timeout):
            try:
                WebDriverWait(self.driver, backoff).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete")
                curr_url = self.driver.current_url
                if not curr_url:
                    raise UrlNotFound("self.driver.current_url is {0}".format(curr_url))
                if self.url_logged != curr_url:
                    border_len = len(curr_url)
                    self.log("")
                    self.log("=" * border_len)
                    self.log("{0}".format(curr_url))
                    self.log("=" * border_len)

                    self.url_logged = curr_url
                common_info = CommonInfo(curr_url, self, [], self.log)
                self.log("===== rescan page {0} =====".format(curr_url), logging.DEBUG)
                _, self.web_components = self.find_components(common_info)
                if not self.web_components:
                    self.web_components = self.find_external_components(
                        common_info)
                break
            except (UrlNotFound,
                    exceptions.JavascriptException,
                    exceptions.WebDriverException,
                    RemoteDisconnected, CustomRemoteDisconnected,
                    exceptions.TimeoutException) as err:
                error = err
                time.sleep(backoff)
        else:
            self.screenshot("page handler")
            if isinstance(error, (RemoteDisconnected, CustomRemoteDisconnected)):
                self.log("Remote disconnection occurred")
                if 'Remote end closed connection without response' in str(error):
                    custom_message = str(error) + ("\nThe error message is http.client.RemoteDisconnected: Remote end "
                                                   "closed connection without response. \n This means that there's no "
                                                   "response at all from the remote end.\n So there's no http headers "
                                                   "or http status code or reason given.\n It might be a network "
                                                   "problem, or possibly the remote server is configured to silently "
                                                   "ignore certain requests  (for example filter by user agent). "
                                                   "Rerun the test.")
                    raise RemoteDisconnected(custom_message) from error
            raise error

        self._click_context = None
        self._input_context = None
        self._select_context = None
        self._table_context = None
        self._data_context = None
        self._canvas_context = None
        self._notification_context = None
        self._error_context = None
        if self._notification_handler:
            for backoff in util.wait_time.generator(0.01, 1, 1):
                try:
                    self._notification_context = None
                    self._notification_handler(self.notification_context)
                    break
                except (exceptions.StaleElementReferenceException,
                        exceptions.WebDriverException):
                    time.sleep(backoff)
        if self.log(log_level=logging.DEBUG):
            self.log("sending mouse event")
        try:
            self.driver.execute_script("""
                                        const mousedownEvent = new MouseEvent('mousedown', {
                                        bubbles: true,
                                        cancelable: true,
                                        button: 0,
                                        });
    
                                        const mouseupEvent = new MouseEvent('mouseup', {
                                        bubbles: true,
                                        cancelable: true,
                                        button: 0,
                                        });
    
                                        document.dispatchEvent(mousedownEvent);
    
                                        setTimeout(() => {
                                        document.dispatchEvent(mouseupEvent);
                                        }, 500);
                                        """)
        except (exceptions.JavascriptException,
                exceptions.WebDriverException) as err:
            error = err
            self.log(f"error occurred while sending mouse event - {error}", logging.DEBUG)

    def reset_web_components(self) -> None:
        """
            clean up all web components, so next access will rescan the page
            :return: None
        """
        self.web_components = []
        self._click_context = None
        self._input_context = None
        self._select_context = None
        self._table_context = None
        self._data_context = None
        self._canvas_context = None
        self._notification_context = None
        self._error_context = None

    def clear_click_context(self) -> None:
        """
            clear click context in component manager.  So the map will get rebuild again, when accessed.
            :return: None
        """
        self._click_context = None
        for component in self.web_components:
            component._parent_context_is_set = False
            component._click_context = None

    @property
    def click_context(self) -> ClickContextMap:
        """
            return aggregated click context from all web components of the page.

            :return: aggregated click context
        """
        if self._click_context is None:
            self._click_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("click context component {0}/{1}".format("/".join(component.css_paths),
                                                                      type(component).__name__))
                for context, value_dict in component.click_context.items():
                    for element_id, element in value_dict.items():
                        self._click_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._click_context

    @property
    def input_context(self) -> InputContextMap:
        """
            return aggregated input context from all web components of the page.

            :return: aggregated input context
        """

        if self._input_context is None:
            self._input_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("input context component {0}/{1}".format("/".join(component.css_paths),
                                                                      type(component).__name__))
                for context, value_dict in component.input_context.items():
                    for element_id, element in value_dict.items():
                        self._input_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._input_context

    @property
    def select_context(self) -> SelectContextMap:
        """
            return aggregated select context from all web components of the page.

            :return: aggregated select context
        """
        if self._select_context is None:
            self._select_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("select context component {0}/{1}".format("/".join(component.css_paths),
                                                                       type(component).__name__))
                for context, value_dict in component.select_context.items():
                    for element_id, element in value_dict.items():
                        self._select_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._select_context

    @property
    def table_context(self) -> TableContextMap:
        """
            return aggregated select context from all web components of the page.

            :return: aggregated select context
        """
        if self._table_context is None:
            self._table_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("table context component {0}/{1}".format("/".join(component.css_paths),
                                                                      type(component).__name__))
                for context, value_dict in component.table_context.items():
                    for element_id, element in value_dict.items():
                        self._table_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._table_context

    @property
    def canvas_context(self) -> CanvasContextMap:
        """
            return aggregated select context from all web components of the page.

            :return: aggregated select context
        """
        if self._canvas_context is None:
            self._canvas_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("canvas context component {0}/{1}".format("/".join(component.css_paths),
                                                                       type(component).__name__))
                for context, value_dict in component.canvas_context.items():
                    for element_id, element in value_dict.items():
                        self._canvas_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._canvas_context

    @property
    def data_context(self) -> DataContextMap:
        """
            return aggregated data context from all web components of the page.

            :return: aggregated data context
        """
        if self._data_context is None:
            self._data_context = {}
            context_list_objs = []
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("data context component {0}/{1}".format("/".join(component.css_paths),
                                                                     type(component).__name__))
                if component.data_context:
                    for context, value_dict in component.data_context.items():
                        for path_contexts, context_obj in value_dict.items():
                            context_map = self._data_context.setdefault(context, {})
                            curr_context = context_map.get(path_contexts, None)
                            if curr_context is None:
                                if isinstance(context_obj, Context):
                                    context_map[path_contexts] = context_obj
                                    if self.log(log_level=logging.DEBUG):
                                        self.log("add context {0} path {1} with element {2}".format(context,
                                                                                                    path_contexts,
                                                                                                    context_obj),
                                                 logging.DEBUG)
                                elif isinstance(context_obj, ContextList):
                                    context_map[path_contexts] = context_obj
                                    context_list_objs.append((context, path_contexts, context_obj))
                                    if self.log(log_level=logging.DEBUG):
                                        self.log("add context {0} path {1} with element {2}".format(context,
                                                                                                    path_contexts,
                                                                                                    context_obj),
                                                 logging.DEBUG)
                                else:
                                    if self.log(log_level=logging.DEBUG):
                                        self.log("skip adding context {0} path {1} with element {2}".format(
                                            context, path_contexts, context_obj))

                            else:
                                # path already exist, see if we can aggregate the data
                                if isinstance(curr_context, ContextList):
                                    if self.log(log_level=logging.DEBUG):
                                        self.log("add {0} to context {1} path {2}".format(context_obj,
                                                                                          context,
                                                                                          path_contexts),
                                                 logging.DEBUG)
                                    curr_context.add(context_obj)
            for context, path_contexts, context_list_obj in context_list_objs:
                if not context_list_obj.contexts and not context_list_obj.allow_empty:
                    # empty context list.  Remove the context
                    self._data_context[context].pop(path_contexts)
                    if not self._data_context[context]:
                        self._data_context.pop(context)

        return self._data_context

    @property
    def notification_context(self) -> NotificationContextMap:
        """
            return aggregated notification context from all web components of the page.

            :return: aggregated notification context
        """
        if self._notification_context is None:
            self._notification_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("notification context component {0}/{1}".format("/".join(component.css_paths),
                                                                             type(component).__name__))
                for context, value_dict in component.notification_context.items():
                    for element_id, element in value_dict.items():
                        self._notification_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._notification_context

    @property
    def error_context(self) -> ErrorContextMap:
        """
            return aggregated error context from all web components of the page.

            :return: aggregated error context
        """
        if self._error_context is None:
            self._error_context = {}
            for component in self.web_components:
                self.iframe_manager.iframes = component.common_info.iframes
                if self.log(log_level=logging.DEBUG):
                    self.log("error context component {0}/{1}".format("/".join(component.css_paths),
                                                                      type(component).__name__))
                for context, value_dict in component.error_context.items():
                    for element_id, element in value_dict.items():
                        self._error_context.setdefault(
                            context, {})[element_id] = element
                        if self.log(log_level=logging.DEBUG):
                            self.log("add context {0} path {1} with element {2}".format(context, element_id, element),
                                     logging.DEBUG)

        return self._error_context
