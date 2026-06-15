"""
page manager definitions
"""
import re
from typing import Callable, Type, Any
import time
import importlib
import inspect
import logging
from functools import wraps
from qali.intersight.gui import page
from qali.intersight.gui import util

PAGE_PATH = page.__package__  # @UndefinedVariable

ALL_CAP_REG = re.compile("^[A-Z][_A-Z0-9]+$")


class PageManager:
    """
        page manager class definition
    """
    page_map = {}
    mask_pattern = re.compile("[Pp]assword")

    def __init__(self, ui) -> None:
        """
            init function of page maanger

            :param ui: intersight ui instance

            :return: None
        """
        self.ui = ui
        self.log = ui.log
        self._curr_url = util.process_url(self.ui.driver.current_url)
        page_def = self._find_page_def(self._curr_url)
        self._curr_page = page_def(self.ui)

    def _find_page_def(self, curr_url: str) -> Type[page.Page]:
        """
            return page class definition base on given curr_url.  

            :param curr_url: url to be used to find page class definition

            :return: page class definition
        """
        self.log("Finding page definition for {0}".format(curr_url), logging.DEBUG)
        if not curr_url or curr_url in ["newtheme", "uirefresh"]:
            self.log("Login page definition found", logging.DEBUG)
            return page.LogInPage
        url = self.ui.driver.current_url
        # regex to match the URL without query parameters
        if re.match("https.*id.cisco.com", url):
            self.log("Login page definition found", logging.DEBUG)
            return page.LogInPage
        return self._find_page_def_from_map(curr_url)

    def _find_page_def_from_map(self, curr_url: str) -> Type[page.Page]:
        """
            return page class definition base on given curr_url.

            :param curr_url: url to be used to find page class definition

            :return: page class definition

        """
        url_paths = tuple(curr_url.split("/"))
        if url_paths in self.page_map:
            if url_paths is not None and self.page_map[url_paths] is not None:
                self.log("Specific page definition found in cache.", logging.DEBUG)
                return self.page_map[url_paths]
            self.log("Default page definition found in cache.", logging.DEBUG)
        else:
            lib_path = PAGE_PATH + "." + ".".join(url_paths)
            try:
                lib_found = importlib.util.find_spec(lib_path)
            except ModuleNotFoundError:
                lib_found = None
            if lib_found:
                page_module = importlib.import_module(lib_path)
                for class_def in reversed(list(page_module.__dict__.values())):
                    if (inspect.isclass(class_def) and
                            issubclass(class_def, page.Page) and
                            class_def != page.Page):
                        self.page_map[url_paths] = class_def
                        self.log("Specific page definition found and added to cache", logging.DEBUG)
                        return class_def
                self.log(f"No Page object definition found in page {lib_path}", logging.DEBUG)
                self.page_map[url_paths] = None

            else:
                self.log(f"Specific page file not found for {lib_path}.  Use default page definition", logging.DEBUG)
                self.page_map[url_paths] = None
        return page.Page

    @property
    def curr_page(self) -> page.Page:
        """
            return current url page object instance 

            :return: current url page object instance 

        """
        curr_url = util.process_url(self.ui.driver.current_url)
        if curr_url != self._curr_url:
            page_def = self._find_page_def(curr_url)
            self._curr_page = page_def(self.ui)
            self._curr_url = curr_url

        return self._curr_page

    def __getattr__(self, attr: str) -> Callable:
        """
            get method attribute value from current page object 

            :param attr: method name of the page object
            :return: current page method
        """

        for backoff in util.wait_time.generator(0.01, 1, self.ui.timeout):
            curr_url = util.process_url(self.ui.driver.current_url)
            if curr_url != self._curr_url:
                page_def = self._find_page_def(curr_url)
                self._curr_page = page_def(self.ui)
                self._curr_url = curr_url

            if hasattr(self._curr_page, attr):
                attr_value = getattr(self._curr_page, attr)
                if callable(attr_value):
                    return self._page_method(attr_value)
                if ALL_CAP_REG.match(attr):
                    # assume it is label since it is all CAP.
                    return attr_value

            if attr.startswith("_"):
                # break any internal variable access, for example
                # _ipython_canary_method_should_not_exist_, which cause unnecessary delay
                break

            self.log("Unable to find attribute {0} for page {1}".format(attr,
                                                                        curr_url), logging.DEBUG)
            time.sleep(backoff)

        self.ui.screenshot(f"page_attribute_{attr}_not_found")
        raise AttributeError("type object '{0}' has no attribute '{1}' with url {2}".format(
            self._curr_page.__class__.__name__,
            attr,
            self.ui.current_url))

    def __dir__(self):
        """
            return dir of the object and curr page.
            :return: dir of the object and curr page const and function
        """
        attributes = []
        curr_page = self._curr_page
        for name in dir(curr_page):
            if callable(getattr(curr_page, name)):
                attributes.append(name)
        return super().__dir__() + attributes

    def _page_method(self, func: Callable) -> Callable:
        """
            wrapper function for page method.  This allow us to log method calls

            :param func: method function to wrap
x            :return: return callable function.
        """

        @wraps(func)
        def func_wrapper(*args, **kargs) -> Any:
            """
                handling actual method call

                :return: function method to return
            """
            func_signature = inspect.signature(func)
            params = func_signature.parameters
            mask_str = "******"
            index = [i for i, s in enumerate(params.keys()) if self.mask_pattern.match(s)]
            args_list = list(args)
            if args_list:
                for idx in index:
                    args_list[idx] = mask_str
            kargs_mod = {key: mask_str if self.mask_pattern.match(key) else value for key, value in kargs.items()}
            msg = f"Calling page method {func.__name__} with args: {args_list} and kargs: {kargs_mod}"

            self.log(msg)
            self.log("-" * min(len(msg), 100))
            rtr = func(*args, **kargs)
            msg = f"Page method {func.__name__} finished"
            self.log("-" * min(len(msg), 100))
            self.log(msg)
            return rtr

        return func_wrapper
