#!/usr/bin/env python
# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fuelmenu.common.urwidwrapper as widget
import subprocess
import urwid
import urwid.raw_display
import urwid.web_display

blank = urwid.Divider()


class shell():
    def __init__(self, parent):
        self.name = "Shell Login"
        self.priority = 90
        self.visible = True
        self.parent = parent
        self.screen = None
        #self.screen = self.screenUI()

    def check(self, args):
        return True

    def start_shell(self, args):
        self.parent.mainloop.screen.stop()
        message = "Type exit to return to the main UI."

        subprocess.call("clear ; echo '%s';echo;bash -i" % message, shell=True)
        self.parent.mainloop.screen.start()

    def refresh(self):
        pass

    def screenUI(self):
        #Define your text labels, text fields, and buttons first
        text1 = urwid.Text("Press the button below to enter a shell login.")
        login_button = widget.Button("Shell Login", self.start_shell)
        #Build all of these into a list
        listbox_content = [text1, blank, login_button]

        #Add everything into a ListBox and return it
        screen = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        return screen
