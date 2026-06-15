"""
Canvas Manager definitions
"""
import pprint
from typing import Callable, Dict, List, Mapping, Optional, Tuple, Union

from qali.intersight.gui.component_manager import ComponentManager
from qali.intersight.gui.iframe_manager import IframeManager
from qali.intersight.gui.model_util import ContextManager, PathContext, context_retry
from qali.intersight.gui.web_component import WebComponent


class CanvasManager(ContextManager):
    """
        Canvas Manager class definition

        Canvas Manager is responsible to find/retry canvas context interaction.

        The manager object is created when canvas_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "canvas_context"

    def __init__(self,
                 context: str,
                 path_contexts: Union[str, PathContext],
                 timeout: int,
                 component_manager: ComponentManager,
                 iframe_manager: IframeManager,
                 log: Callable,
                 screenshot: Callable,
                 page_errors: Callable) -> None:
        """
            init fucntion for table manager

            :param context: context for canvas action
            :param path_contexts: path context for canvas action.  This is mainly used as tie breaker
            :param timeout: time to wait for context to be ready
            :param component_manager:  component manager instance
            :param iframe_manager:  iframe manager instance
            :param log: logging function
            :param screenshot: screenshot function
            :param page_errors: page_errors function

            :return: None

        """
        super().__init__(context,
                         path_contexts,
                         timeout,
                         component_manager,
                         iframe_manager,
                         log,
                         screenshot,
                         page_errors)
        self._canvas_name = None

    def repr(self) -> str:
        """
            return representation string of table context

            :return: representation string of table context
        """
        if self.path_contexts is None:
            return str(("canvas", self.context))
        return str(("canvas", (self.context, self.path_contexts)))

    @property
    def canvas_name(self) -> str:
        """
            return name of the table.  Mainly for loggign purpose

            :return: table name
        """
        if self._canvas_name is None:
            self._canvas_name = "{0} canvas".format(
                self.context_name) if self.context else "canvas"
        return self._canvas_name

    @context_retry(6)
    def add_task(self,
                 name: str,
                 node_name: str = None,
                 x_offset: Optional[int] = None,
                 y_offset: Optional[int] = None,
                 use_search: bool = False,
                 timeout: Optional[int] = None) -> None:
        """
            add task to workflow canvas

            :param name: name of task to be added.
            :param node_name: node name to drop the task to.
            :param x_offset: x coordinate on where to drop the task.
                             The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the task.
                             The coordinate is relative to top left of canvas.
            :param use_search: whether to use search box to find the task
            :param timeout: time to wait for element to be ready.

            :return: None
        """

        self.curr_context.add_task(name, node_name, x_offset, y_offset, use_search)
        self.log(f"Added task {name} to {self.canvas_name}")

    @context_retry(6)
    def add_workflow(self,
                     name: str,
                     node_name: str = None,
                     x_offset: Optional[int] = None,
                     y_offset: Optional[int] = None,
                     use_search: bool = False,
                     timeout: Optional[int] = None) -> None:
        """
            add workflow to workflow canvas

            :param name: name of workflow to be added.
            :param node_name: node name to drop the workflow to.  This is mainly for parallel loop or serial loop.
                              But can also be use as drop location.  This is only applicable when x_offset and y_offset
                              is None.
            :param x_offset: x coordinate on where to drop the workflow.
                             The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the workflow.
                             The coordinate is relative to top left of canvas.
            :param timeout: time to wait for element to be ready.
            :param use_search: whether to use search box to find the workflow

            :return: None
        """

        self.curr_context.add_workflow(name, node_name, x_offset, y_offset, use_search)
        self.log(f"Added workflow {name} to {self.canvas_name}")

    @context_retry(6)
    def add_operation(self,
                      name: str,
                      node_name: str = None,
                      x_offset: Optional[int] = None,
                      y_offset: Optional[int] = None,
                      use_search: bool = False,
                      timeout: Optional[int] = None) -> None:
        """
            add operation to workflow canvas

            :param name: name of operation to be added.
            :param node_name: node name to drop the workflow to.  This is mainly for parallel loop or serial loop.
                              But can also be use as drop location.  This is only applicable when x_offset and y_offset
                              is None.
            :param x_offset: x coordinate on where to drop the operation.
                             The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the operation.
                             The coordinate is relative to top left of canvas.
            :param use_search: whether to use search box to find the operation
            :param timeout: time to wait for element to be ready.

            :return: None
        """

        self.curr_context.add_operation(name, node_name, x_offset, y_offset, use_search)
        self.log(f"Added operation {name} to {self.canvas_name}")

    @context_retry(5)
    def connect_nodes(self,
                      src_node: str,
                      dst_node: str,
                      success: bool = True,
                      condition_index: Optional[int] = None,
                      timeout: Optional[int] = None) -> None:
        """
            connect node in the canvas
            :param src_node: source node to connect
            :param dst_node: destination node to connect
            :param success: True if the connect success path.  Otherwise, connect failure path
            :param condition_index: condition point to connect.  Only applicable to condition task.  Index start with 0
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.connect_nodes(src_node, dst_node, success, condition_index)
        path_name = "success" if success else "failure"
        self.log(f"Connected node {src_node} to node {dst_node} with {path_name}")

    @context_retry(4)
    def disconnect_node(self,
                        src_node: str,
                        success: bool = True,
                        condition_index: Optional[int] = None,
                        timeout: Optional[int] = None) -> None:
        """
            disconnect node in the canvas
            :param src_node: source node to connect
            :param success: True if the connect success path.  Otherwise, connect failure path
            :param condition_index: condition point to connect.  Only applicable to condition task.  Index start with 0
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.disconnect_node(src_node, success, condition_index)
        path_name = "success" if success else "failure"
        self.log(f"Disconnected {path_name} line from node {src_node}")

    @context_retry(1)
    def zoom_out(self, timeout: Optional[int] = None) -> bool:
        """
            click zoom out once if it is not disabled
            :param timeout: time to wait for element to be ready.
            :return: return True if zoom_out is clicked
        """
        rtr = self.curr_context.zoom_out()
        if rtr:
            self.log("clicked zoom out on the canvas toolbar")
        else:
            self.log("zoom out click skipped, since it is disabled")
        return rtr

    @context_retry(1)
    def zoom_in(self, timeout: Optional[int] = None) -> bool:
        """
            click zoom in once if it is not disabled
            :param timeout: time to wait for element to be ready.
            :return: return True if zoom_out is clicked
        """
        rtr = self.curr_context.zoom_in()
        if rtr:
            self.log("clicked zoom in on the canvas toolbar")
        else:
            self.log("zoom in click skipped, since it is disabled")
        return rtr

    @context_retry(1)
    def enable_full_screen(self, timeout: Optional[int] = None) -> bool:
        """
            click fullScreen action once if it is not disabled
            :return: return True if fullScreen is clicked
        """
        rtr = self.curr_context.enable_full_screen()
        if rtr:
            self.log("clicked enable fullScreen on the canvas toolbar")
        else:
            self.log("enable fullScreen click skipped, since it is disabled")
        return rtr

    @context_retry(1)
    def click_on_legend(self, timeout: Optional[int] = None) -> bool:
        """
            click legend action once if it is not disabled
            :return: return True if legend is clicked
        """
        rtr = self.curr_context.click_on_legend()
        if rtr:
            self.log("clicked legend on the canvas toolbar")
        else:
            self.log("legend click skipped, since it is disabled")
        return rtr

    @context_retry(1)
    def disable_full_screen(self, timeout: Optional[int] = None) -> bool:
        """
            click fullScreen action once if it is not disabled
            :return: return True if fullScreen is clicked
        """
        rtr = self.curr_context.disable_full_screen()
        if rtr:
            self.log("clicked disable fullScreen on the canvas toolbar")
        else:
            self.log("disable fullScreen click skipped, since it is disabled")
        return rtr

    @context_retry(2)
    def search_node(self, name: str, timeout: Optional[int] = None) -> bool:
        """
            search and select device from the toolbar search box
            :param name: node name
            :return: return True if node is selected
        """
        rtr = self.curr_context.search_node(name)
        if rtr:
            self.log(f"node: {name} was found and selected successfully")
        else:
            self.log(f"node: {name} was not found and selected")
        return rtr

    @context_retry(2)
    def select_node(self, node_id: str, timeout: Optional[int] = None) -> bool:
        """
            select node by id
            :param node_id: node id
            :return: return True if device is selected
        """
        rtr = self.curr_context.select_node(node_id)
        if rtr:
            self.log(f"node: {node_id} was selected successfully")
        else:
            self.log(f"node {node_id} was not selected")
        return rtr

    @context_retry(1)
    def auto_workflow_align(self, timeout: Optional[int] = None) -> None:
        """
            click auto workflow align
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.auto_workflow_align()
        self.log("clicked auto workflow align on the canvas toolbar")

    @context_retry(1)
    def nodes_info(self, show_child: Optional[bool] = False,
                   timeout: Optional[int] = None) -> Mapping[str, Tuple[str, Mapping[str, Union[int, float]]]]:
        """
            return node name, node label and position mapping table.

            :param timeout: time to wait for element to be ready.
            :return: node name, node label and position mapping table.
        """
        rtr = self.curr_context.nodes_info(show_child, timeout)
        self.log(f"Current nodes in the canvas\n{pprint.pformat(rtr)}")
        return rtr

    @context_retry(1)
    def ports_info(self, node_id: str,
                   timeout: Optional[int] = 0) -> Mapping[str, Tuple[str, Mapping[str, Union[int, float]]]]:
        """
            return port name, port label and position mapping table.

            :param timeout: time to wait for element to be ready.
            :return: port name, port label and position mapping table.
        """
        rtr = self.curr_context.ports_info(node_id, timeout)
        self.log(f"Current ports for the given node in the canvas\n{pprint.pformat(rtr)}")
        return rtr

    @context_retry(1)
    def edges_info(self, timeout: Optional[int] = None) -> List[Tuple[str, Mapping[str, Union[int, float]]]]:
        """
            return list of edges
            :return: list of edges
        """
        rtr = self.curr_context.edges_info()
        self.log(f"Current edges in the canvas\n{pprint.pformat(rtr)}")
        return rtr

    @context_retry(3)
    def add_node(self,
                 name: str,
                 use_search: bool = False,
                 timeout: Optional[int] = None) -> None:
        """
            add node to workflow canvas

            :param name: name of task to be added.
            :param use_search: whether to use search box to find the node
            :param timeout: time to wait for element to be ready.
            :return: None
        """

        self.curr_context.add_node(name, use_search)
        self.log(f"Added node {name} to {self.canvas_name}")

    @context_retry(2)
    def delete_node(self, node: str = None, timeout: Optional[int] = None) -> None:
        """
            delete given node from canvas

            :param node: node to delete
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.delete_node(node)
        self.log(f"Delete node {node} from {self.canvas_name}")

    @context_retry(2)
    def edit_node(self, node: str = None, timeout: Optional[int] = None) -> None:
        """
            edit given node from canvas

            :param node: node to edit
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.edit_node(node)
        self.log(f"clicked node {node} from {self.canvas_name}")

    @context_retry(3)
    def expand_node(self, node: str = None, expand=True, timeout: Optional[int] = None) -> bool:
        """
            expand given node from canvas

            :param node: node to expand
            :param expand: expand or collapse node
            :param timeout: time to wait for element to be ready.
            :return: return True if action is taken to expand or collapse
        """
        rtr = self.curr_context.expand_node(node, expand)
        if expand:
            self.log(f"Expanded node {node} from {self.canvas_name}")
        else:
            self.log(f"Collapsed node {node} from {self.canvas_name}")
        return rtr

    @context_retry(2)
    def get_node_details(self, node_id: str, timeout: Optional[int] = None):
        """
            get node details by hover over on it

            :param node_id: node id to display details
            :param timeout: time to wait for element to be ready. 
        """
        return self.curr_context.get_node_details(node_id)

    @context_retry(2)
    def get_node_alarms(self, node_id: str, timeout: Optional[int] = None):
        """
            get node alarms by hover over on it

            :param node_id: node id to display details
            :param timeout: time to wait for element to be ready.
        """
        return self.curr_context.get_node_alarms(node_id, timeout)

    @context_retry(2)
    def go_to_topology(self, moid: Optional[str] = None, node_id: Optional[str] = None, timeout: Optional[int] = None):
        """
            go to the topology by device moid (node)

            :param moid: node moid
            :param mode_id: node id
            :param timeout: time to wait for element to be ready
        """
        self.curr_context.go_to_topology(moid, node_id)

    @context_retry(2)
    def click_on_tooltip(self, moid: Optional[str] = None,
                         node_id: Optional[str] = None,
                         button_label: Optional[str] = '',
                         timeout: Optional[int] = 1):
        """
            go to the topology by device moid (node)

            :param moid: node moid
            :param mode_id: node id
            :param timeout: time to wait for element to be ready
        """
        self.curr_context.click_on_tooltip(moid, node_id, button_label)

    @context_retry(2)
    def get_tooltip_choices(self, moid: Optional[str] = None,
                            node_id: Optional[str] = None,
                            timeout: Optional[int] = None):
        """
            get tooltip click choices by device moid (node)

            :param moid: node moid
            :param mode_id: node id
            :param timeout: time to wait for element to be ready
        """
        return self.curr_context.get_tooltip_choices(moid, node_id, timeout)

    @context_retry(2)
    def navigate_by_breadcrumbs(self, name: str, timeout: Optional[int] = None):
        """
            go to the topology by device name through the breadcrubms

            :param name: device name
        """
        self.curr_context.navigate_by_breadcrumbs(name)

    # data related methods
    @context_retry(1)
    def is_app_mounted(self, timeout: Optional[int] = None) -> bool:
        """
            whether application mounted or not

            :return: return True if application has been mounted
        """
        return self.curr_context.is_app_mounted()

    @context_retry(1)
    def get_popover(self, timeout: Optional[int] = None) -> WebComponent:
        """
            get popover web element

            :return: return popover web element
        """
        return self.curr_context.get_popover()

    @context_retry(1)
    def get_breadcrumbs_data(self, timeout: Optional[int] = None):
        """
            get breadcrumbs data from workspace header

            :return: breadcrumbs data values
        """
        return self.curr_context.get_breadcrumbs_data()

    @context_retry(2)
    def get_node_id(self, config, timeout: Optional[int] = None):
        """
            get node id by config

            :param config: data config
            :return: node id
        """
        return self.curr_context.get_node_id(config)

    @context_retry(2)
    def get_node_coordinates(self, node_id: str, timeout: Optional[int] = None):
        """
            get node coordinates by name

            :param node_id: node id
            :return: coordinates in format: { x: float, y: float }
        """
        return self.curr_context.get_node_coordinates(node_id)

    @context_retry(4)
    def move_node(self, node: str, x_coordinate: int, y_coordinate: int, timeout: Optional[int] = None) -> None:
        """
            move given node to given canvas position

            :param node: node to move
            :param x_coordinate: x coordinate.  Scale is 0-100 and from left to right (i.e right most is 0)
            :param y_coordinate: y coordinate.  Scale is 0-100 and from top to bottom (i.e top most is 0)
            :param timeout: time to wait for element to be ready.
            :return: None
        """
        self.curr_context.move_node(node, x_coordinate, y_coordinate)
        self.log(f"Moved node {node} to x={x_coordinate}, y={y_coordinate} in {self.canvas_name}")

    @context_retry(1)
    def delete(self, timeout: Optional[int] = None) -> None:
        """
            delete given node from canvas

            :param node: node to delete
            :return: None
        """
        self.curr_context.delete()
        self.log(f"delete {self.canvas_name}")

    @context_retry(1)
    def edit(self, timeout: Optional[int] = None) -> None:
        """
            edit given node from canvas

            :param node: node to edit
            :return: None
        """
        self.curr_context.edit()
        self.log(f"clicked {self.canvas_name}")

    @context_retry(2)
    def get_marker_tooltip_data(self, marker_id: str, timeout: Optional[int] = None) -> Dict:
        """
            get marker tooltip data by marker id
            :param marker_id: id of the marker
            :param timeout: time to wait for element to be ready.
            :return: return tooltip data dictionary
        """
        rtr = self.curr_context.get_marker_tooltip_data(marker_id, timeout)
        self.log(f"Retrieved tooltip data for marker '{marker_id}': {pprint.pformat(rtr)}")
        return rtr

    @context_retry(1)
    def reset_zoom(self, timeout: Optional[int] = None) -> bool:
        """
            click reset zoom to default view
            :param timeout: time to wait for element to be ready.
            :return: return True if reset zoom is clicked
        """
        return self.curr_context.reset_zoom()

    @context_retry(1)
    def toggle_selection_mode(self, timeout: Optional[int] = None) -> bool:
        """
            toggle selection mode for area selection
            :param timeout: time to wait for element to be ready.
            :return: return True if selection mode is toggled
        """
        return self.curr_context.toggle_selection_mode()

    @context_retry(1)
    def click_map_info_button(self, timeout: Optional[int] = None) -> bool:
        """
            click map info button
            :param timeout: time to wait for element to be ready.
            :return: return True if info button is clicked
        """
        return self.curr_context.click_map_info_button()

    @context_retry(1)
    def click_map_widget_button(self, timeout: Optional[int] = None) -> bool:
        """
            click map widget button to toggle chart panel
            :param timeout: time to wait for element to be ready.
            :return: return True if widget button is clicked
        """
        return self.curr_context.click_map_widget_button()
