"""Source-style *working* command links for original PageStart.

The user's 2026-11-16 original screenshot shows borderless blue link
captions, secondary notes, large standalone glyphs, and no raised white
card tiles. This QWidget subclass preserves the actual original DFM
QPushButton rectangles, clicked signals, focus and Core routes; only
painting is approximate. All icons below are PROCEDURAL Qt candidates,
not private image-list bits from the original EXE/DFM.
"""
from __future__ import annotations

from math import cos, pi, sin

from PySide6.QtCore import Qt, QPointF, QRect, QSize
from PySide6.QtGui import (
    QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import QPushButton


SOURCE="SOURCE_OPERATOR_SCREENSHOT_START_COMMAND_QT_CANDIDATE_STAGE111Z31CP"
TITLE_COLOUR="#037acb"
DETAIL_COLOUR="#318fd1"


def _gear(p, cx, cy, radius, fill):
    pts=[]
    for n in range(36):
        angle=2*pi*n/36
        edge=(radius if n%3 else radius*.8)
        pts.append(QPointF(cx+cos(angle)*edge,cy+sin(angle)*edge))
    p.setPen(QPen(QColor("#59616b"),1.2))
    p.setBrush(QBrush(QColor(fill)))
    p.drawPolygon(QPolygonF(pts))
    p.setBrush(QBrush(QColor("#f5f7f8")))
    p.drawEllipse(QPointF(cx,cy),radius*.28,radius*.28)


def _qt_source_icon(name: str) -> QIcon:
    """Original Gears/Open/EditGear/EditNet shape, candidate vector paint."""
    pm=QPixmap(56,56)
    pm.fill(Qt.transparent)
    p=QPainter(pm)
    try:
        p.setRenderHint(QPainter.Antialiasing,True)
        if name=="Gears":
            _gear(p,21,21,15,"#d1d3d7")
            _gear(p,38,38,10,"#e7c896")
        elif name=="Open":
            p.setPen(QPen(QColor("#81703d"),1.5))
            p.setBrush(QBrush(QColor("#f7e2a1")))
            p.drawRoundedRect(QRect(5,14,28,26),3,3)
            p.setBrush(QBrush(QColor("#dbc077")))
            p.drawPolygon(QPolygonF([
                QPointF(3,22),QPointF(47,22),QPointF(40,43),
                QPointF(3,43)]))
            p.setPen(QPen(QColor("#ad914c"),1.2))
            p.drawLine(6,24,40,24)
        else:
            # A source-like grey command page with an edit pencil, rather
            # than Qt's unrelated blue computer/file-list icons.
            p.setPen(QPen(QColor("#56656c"),1.4))
            p.setBrush(QBrush(QColor("#e5ebed")))
            p.drawRect(QRect(8,6,30,41))
            p.setPen(QPen(QColor("#7e8b93"),1))
            p.drawRect(QRect(13,11,17,12))
            p.drawLine(13,29,32,29)
            p.drawLine(13,34,25,34)
            if name=="EditGear":
                _gear(p,21,18,6,"#f5f5f5")
            p.setPen(QPen(QColor("#365b4d"),1.5))
            p.setBrush(QBrush(QColor("#6bab83")))
            p.drawPolygon(QPolygonF([
                QPointF(29,39),QPointF(44,23),QPointF(48,27),
                QPointF(32,43),QPointF(27,44)]))
            p.setBrush(QBrush(QColor("#d7a06c")))
            p.drawPolygon(QPolygonF([
                QPointF(27,44),QPointF(29,39),QPointF(32,43)]))
    finally:
        p.end()
    return QIcon(pm)


class SourceStartCommandButton(QPushButton):
    """A real QPushButton with original-blue image-caption-note painting."""

    def __init__(self,title: str,note: str,image_name: str,parent):
        super().__init__(title,parent)
        if not isinstance(note,str) or len(note)>180:
            raise ValueError("A bounded source command note is required")
        self.source_note=note
        self.setFlat(True)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setIcon(_qt_source_icon(image_name))
        self.setIconSize(QSize(56,56))
        self.setProperty("sourceTaskCommandImageCandidate",True)
        self.setProperty("sourceTaskNoRaisedCardBorder",True)
        self.setProperty("sourceOriginalCommandBitmapProvided",False)
        self.setProperty("sourceSecondaryCaption",note)
        self.setProperty("sourceCommandWidgetIsClickable",True)

    def paintEvent(self,event):
        p=QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing,True)
            if self.isDown():
                p.fillRect(self.rect(),QColor(165,221,252,90))
            elif self.underMouse():
                p.fillRect(self.rect(),QColor(215,244,255,64))
            if self.hasFocus():
                p.setPen(QPen(QColor("#5a9dc9"),1,Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRect(self.rect().adjusted(1,1,-2,-2))
            mode=QIcon.Normal if self.isEnabled() else QIcon.Disabled
            self.icon().paint(p,QRect(8,14,52,52),Qt.AlignCenter,mode)
            font=QFont("Tahoma")
            font.setPixelSize(13)
            font.setUnderline(self.underMouse())
            p.setFont(font)
            p.setPen(QColor(TITLE_COLOUR if self.isEnabled() else "#88959d"))
            p.drawText(QRect(74,9,max(0,self.width()-79),29),
                       Qt.AlignLeft|Qt.AlignVCenter,self.text())
            if self.source_note:
                font.setUnderline(False)
                font.setPixelSize(11)
                p.setFont(font)
                p.setPen(QColor(DETAIL_COLOUR if self.isEnabled()
                                else "#9da9b1"))
                p.drawText(QRect(74,36,max(0,self.width()-79),40),
                           Qt.AlignLeft|Qt.AlignTop|Qt.TextWordWrap,
                           self.source_note)
        finally:
            p.end()
