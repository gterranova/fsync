#!/usr/bin/python
# -*- coding: UTF-8 -*-

#!/usr/bin/python

# repository.py

import wx
import sys
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin

class CheckListCtrl(wx.ListCtrl, CheckListCtrlMixin, ListCtrlAutoWidthMixin):
    def __init__(self, parent):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT | wx.SUNKEN_BORDER)
        CheckListCtrlMixin.__init__(self)
        ListCtrlAutoWidthMixin.__init__(self)


class ActionsDialog(wx.Dialog):
    def __init__(self, parent, id, title, actions):
        wx.Dialog.__init__(self, parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE, size=(450, 400))

        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        leftPanel = wx.Panel(self, -1)
        rightPanel = wx.Panel(self, -1)

        self.actions = []
        self.list = CheckListCtrl(rightPanel)
        self.list.InsertColumn(0, 'Action', width=140)
        self.list.InsertColumn(1, 'File')

        for i in actions:
            index = self.list.InsertStringItem(sys.maxint, i[0])
            self.list.SetStringItem(index, 1, i[1])

        vbox2 = wx.BoxSizer(wx.VERTICAL)

        sel = wx.Button(leftPanel, -1, 'Select All', size=(100, -1))
        des = wx.Button(leftPanel, -1, 'Deselect All', size=(100, -1))
        apply = wx.Button(leftPanel, -1, 'Apply', size=(100, -1))
        cancel = wx.Button(leftPanel, -1, 'Cancel', size=(100, -1))        


        self.Bind(wx.EVT_BUTTON, self.OnSelectAll, id=sel.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnDeselectAll, id=des.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnApply, id=apply.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancel.GetId())        

        vbox2.Add(sel, 0, wx.TOP, 5)
        vbox2.Add(des)
        vbox2.Add(apply)
        vbox2.Add(cancel)

        leftPanel.SetSizer(vbox2)

        vbox.Add(self.list, 1, wx.EXPAND | wx.TOP, 3)
        vbox.Add((-1, 10))
        rightPanel.SetSizer(vbox)

        hbox.Add(leftPanel, 0, wx.EXPAND | wx.RIGHT, 5)
        hbox.Add(rightPanel, 1, wx.EXPAND)
        hbox.Add((3, -1))

        self.SetSizer(hbox)
        self.Layout()
        self.Centre()

    def OnSelectAll(self, event):
        num = self.list.GetItemCount()
        for i in range(num):
            self.list.CheckItem(i)

    def OnDeselectAll(self, event):
        num = self.list.GetItemCount()
        for i in range(num):
            self.list.CheckItem(i, False)

    def OnApply(self, event):
        num = self.list.GetItemCount()
        actions = []
        for i in range(num):
            if self.list.IsChecked(i):
                actions.append( (self.list.GetItemText(i),
                                self.list.GetItem(i, 1).GetText()) )
        self.actions = actions
        self.Close()
        
    def OnCancel(self, event):
        self.Close()
        
