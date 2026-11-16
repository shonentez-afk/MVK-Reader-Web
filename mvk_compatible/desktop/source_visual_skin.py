"""Stage111Z31CL visible Delphi source shell, with opt-in private image loader.

This is a real Qt presentation layer for existing Core and PageAdc/Spec
controllers, NOT a substitute for source float32/FFT/FRange, nor a claim
of source Win32 bitmap/font/pixel parity. The operator can open their
own mvkform.dfm as private, in-memory TPicture data; no original assets
or paths are ever embedded in this public repository or CI artifacts.

Default source mode removes research-only window chrome and retains
keyboard actions: Ctrl+O for a local measurement, Ctrl+D for current
research, F12 to show/hide the compatible Qt technical interface.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QRect, QPoint
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QPushButton, QStyle, QWidget, QToolButton,
)

from ..core.original_pagestart_private_pictures import (
    source_start_pictures_from_dfm,
)
from ..core.original_private_imagelist import source_task_icons_from_dfm
from ..core.original_runtime_tabs import (
    original_runtime_visible_pages,original_runtime_tab_contract,
)
from ..core.original_ui_form_contract import (
    ORIGINAL_ROOT_PAGES, ORIGINAL_SPECTRUM_CONTROLS,
    ORIGINAL_WAVE_CONTROLS,
)

SOURCE="SOURCE_DERIVED_ORIGINAL_SHELL_GEOMETRY_STAGE111Z31CL"

# Native DFM image names are evidence, NOT bundled original bitmaps.
# Qt icons are explicitly candidates when the operator hasn't supplied
# their own extracted sources.
_TAB_FALLBACK={
    "PageStart":"SP_DirHomeIcon",
    "PageConfig":"SP_ComputerIcon",
    "PageStatus":"SP_FileDialogDetailedView",
    "PageAdc":"SP_MediaPlay",
    "PageSpectrum":"SP_FileDialogContentsView",
    "PageFile":"SP_DialogOpenButton",
    "PageCalib":"SP_DialogApplyButton",
}
_COMMAND_FALLBACK={
    "bAdcEnvelopeType":"SP_DialogResetButton",
    "bAdcType":"SP_MediaPlay",
    "bAdcHScale":"SP_ArrowRight",
    "bAdcVScale":"SP_ArrowUp",
    "bSpecEnvelopeType":"SP_DialogResetButton",
    "bSpecType":"SP_FileDialogContentsView",
    "bSpecLines":"SP_FileDialogDetailedView",
    "bSpecHScale":"SP_ArrowRight",
    "bSpecVScale":"SP_ArrowUp",
    "bSpecCopyValue":"SP_DialogApplyButton",
    "bSpecSaveValue":"SP_DialogSaveButton",
}
_START_RIGHT_DESIGN_WIDTH=257
_START_LOGO_RECT=(3,568,432,120)
# Reference: the operator's raw 1920x1020 144-DPI original idle screenshot:
# left RGB ~252/254/255, center ~224/245/255, x1536 ~205/239/255.
# The older private DFM happens to contain AMBER TBitmap palettes, despite
# the observed original runtime being cyan. ImageList icons from that DFM
# still match; incompatible backgrounds MUST NOT supersede runtime evidence.
_START_FALLBACK_PALETTE=("#fcfeff","#ccefff")



class SourceStartBackdrop(QWidget):
    """Original TImage docking, with source-color placeholder or private DFM.

    Native DFM stretches imBackL to the remaining client area and
    imBackR to 257 logical px on the RIGHT. Source imLogo remains at
    (3,568,432,120). In the absence of private operator-provided DFM
    pictures, the warm background is a visibly approximate fallback.
    """
    def __init__(self,parent):
        super().__init__(parent)
        self.setObjectName("SourcePageStartLauncher")
        self._private_pictures={}
        self._private_task_icons={}
        self._private_blue_backgrounds_compatible=False
        self._original_assets_loaded=False
        self.setProperty("sourceOriginalBitmapParityVerified",False)
        self.setProperty("sourceBackgroundOriginalDfmGeometry",True)
        self.setProperty("sourceContainsPublishedVendorImageData",False)
        # Original imLogo remains private. Procedural approximate logo is
        # shown in short native DPI150 windows instead of being clipped.
        self.logo=QLabel(self)
        self.logo.setObjectName("imLogo")
        self.logo.setGeometry(*_START_LOGO_RECT)
        self.logo.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.logo.setPixmap(self._make_fallback_logo())
        self.logo.setToolTip(
            "Оригинальный imLogo 432×120 не включён в сборку. "
            "Только локальная копия mvkform.dfm может показать точный ресурс.")
        self.logo.setProperty("originalDfmLogicalRect",_START_LOGO_RECT)
        self.logo.setProperty("originalAssetLoadedPrivately",False)
        self.logo.lower()
        self.setProperty("sourceBlueReferenceCandidate",True)
        self.setProperty("sourceLogoResponsiveToShortWindow",True)
        self.setProperty("sourceOperatorScreenshotPixelParityVerified",False)
        self.setProperty("sourcePrivateDfmPaletteAcceptedForBackground",False)
        self.setProperty("sourceOriginalIconCollectionLoaded",False)
        candidate=os.environ.get("MVKVIEW_PRIVATE_SOURCE_DFM","")
        if candidate:
            # Explicit opt-in only. Wrong or missing paths are NOT searched
            # across the user's disk and never become startup blockers.
            try:
                self.load_private_original_dfm(candidate)
            except (OSError,ValueError):
                pass

    @staticmethod
    def _make_fallback_logo():
        """Only a Qt-drawn preview; the actual original logo stays private."""
        pixmap=QPixmap(432,120)
        pixmap.fill(Qt.transparent)
        painter=QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.Antialiasing,True)
            painter.setPen(QPen(QColor("#e51d2b"),3))
            line=[QPoint(20,96),QPoint(35,96),QPoint(41,82),
                  QPoint(47,111),QPoint(53,70),QPoint(61,96),
                  QPoint(218,96)]
            for begin,end in zip(line,line[1:]):
                painter.drawLine(begin,end)
            font=QFont("Tahoma")
            font.setPixelSize(24)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#141414"))
            painter.drawText(67,86,"ВАСТ")
            font.setPixelSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(66,110,"©2021 ООО «АССОЦИАЦИЯ ВАСТ»")
        finally:
            painter.end()
        return pixmap

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # Source DFM preferred y=568 is preserved at full-height. When
        # native Qt DPI150 reduces the client below 688 logical pixels,
        # keep logo visible without changing its *source DFM* metadata.
        x,y,w,h=_START_LOGO_RECT
        actual_y=min(y,max(0,self.height()-h))
        self.logo.setGeometry(x,actual_y,w,h)
        self.setProperty("sourceLogoActualQtTop",actual_y)

    @property
    def original_pictures_loaded_privately(self):
        return self._original_assets_loaded

    @property
    def private_task_icons(self):
        """Only transient QPixmaps; no originals ever leave this process."""
        return dict(self._private_task_icons)

    @property
    def private_blue_backgrounds_compatible(self):
        return self._private_blue_backgrounds_compatible

    @staticmethod
    def _looks_like_observed_blue_background(pixmap):
        img=pixmap.toImage()
        color=img.pixelColor(img.width()//2,img.height()//2)
        return (color.blue()>=color.red()+5 and
                color.blue()>=color.green()+2)

    def load_private_original_dfm(self,path):
        """One explicit local DFM; no writing/copying/private file logging."""
        p=Path(path)
        if not p.is_file() or p.stat().st_size>12*1024*1024:
            raise ValueError("Choose a bounded local original mvkform.dfm")
        stream=p.read_bytes()
        original=source_start_pictures_from_dfm(stream)
        pixmaps={}
        for name,item in original.items():
            pixmap=QPixmap()
            if not pixmap.loadFromData(item.bytes,item.format):
                raise ValueError("Original local TPicture could not be decoded")
            if (pixmap.width()<1 or pixmap.height()<1
                    or pixmap.width()>4096 or pixmap.height()>4096):
                raise ValueError("Original TPicture dimensions out of bounds")
            pixmaps[name]=pixmap
        # Read original task images strictly from the LOCAL file. If this
        # older DFM has no image collection, preserve compatible fallbacks.
        icons={}
        try:
            for name,private in source_task_icons_from_dfm(stream).items():
                pm=QPixmap()
                if not pm.loadFromData(private.data,"PNG"):
                    raise ValueError("Invalid in-memory icon PNG")
                icons[name]=pm
        except ValueError:
            icons={}
        self._private_pictures=pixmaps
        self._private_task_icons=icons
        self._original_assets_loaded=True
        # DFM alone does NOT establish that its fixed, amber BMPs match
        # the user's actual CYAN runtime. Do not undo the blue PageStart
        # when this earlier source file has the incompatible palette.
        self._private_blue_backgrounds_compatible=all(
            self._looks_like_observed_blue_background(pixmaps[name])
            for name in ("imBackL","imBackR"))
        self.setProperty("sourcePrivateDfmPaletteAcceptedForBackground",
                         self._private_blue_backgrounds_compatible)
        self.setProperty("sourceOriginalIconCollectionLoaded",bool(icons))
        self.logo.setPixmap(pixmaps["imLogo"])
        self.logo.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        self.logo.setToolTip(
            "Точное изображение imLogo загружено в память из "
            "выбранного локального DFM. Исходные байты не сохраняются.")
        self.logo.setProperty("originalAssetLoadedPrivately",True)
        self.setProperty("sourceOriginalBitmapParityVerified",False)
        self.update()
        return tuple(sorted(pixmaps))

    def paintEvent(self,event):
        painter=QPainter(self)
        try:
            width=max(0,self.width())
            height=max(0,self.height())
            right=min(_START_RIGHT_DESIGN_WIDTH,width)
            left=width-right
            if (self._original_assets_loaded and
                    self._private_blue_backgrounds_compatible):
                painter.drawPixmap(QRect(0,0,left,height),
                                   self._private_pictures["imBackL"])
                painter.drawPixmap(QRect(left,0,right,height),
                                   self._private_pictures["imBackR"])
            else:
                # The operator's full original screenshot shows a uniform
                # cyan/white gradient LEFT and checkerboard only on the
                # right (actual 144-DPI window, not the older amber DFM).
                gradient=QLinearGradient(0,0,max(1,left),0)
                gradient.setColorAt(0,QColor(_START_FALLBACK_PALETTE[0]))
                gradient.setColorAt(1,QColor(_START_FALLBACK_PALETTE[1]))
                painter.fillRect(QRect(0,0,left,height),QBrush(gradient))
                painter.fillRect(QRect(left,0,right,height),
                                 QColor(_START_FALLBACK_PALETTE[1]))
                tile=18
                for xx in range(left,width,tile):
                    progress=(xx-left)/max(1,right)
                    visibility=min(.72,max(0.,(progress-.25)/.75))
                    for yy in range(0,height,tile):
                        if ((xx-left)//tile+yy//tile)%2==0:
                            colour=QColor(255,255,255,round(185*visibility))
                        else:
                            colour=QColor(42,170,240,round(35*visibility))
                        painter.fillRect(QRect(xx,yy,min(tile,width-xx),
                                               min(tile,height-yy)),colour)
        finally:
            painter.end()


class OriginalVisualSkin:
    """Make SOURCE pages primary; keep all research controls available."""

    def __init__(self,window,view_menu):
        self.window=window
        self.source=SOURCE
        self.technical=False
        self.home=window.task_subpages.widget(0)
        self.start=window.original_start_controller
        self.root=window.original_root_tabs
        self._source_style()
        self._source_icons()
        self._visibility_guard=False
        self.root.currentChanged.connect(
            lambda *_:self.update_runtime_tabs())
        self._configure_visibility(False)

        self.toggle_action=QAction(
            "Показать технический интерфейс Qt",window)
        self.toggle_action.setObjectName(
            "actionToggleSourceCompatibleTechnicalUI")
        self.toggle_action.setCheckable(True)
        self.toggle_action.setShortcut("F12")
        self.toggle_action.toggled.connect(self._configure_visibility)
        # A shortcut on QMainWindow remains usable when the menu is hidden.
        window.addAction(self.toggle_action)
        view_menu.addAction(self.toggle_action)

        private=QAction(
            "Открыть оригинальные изображения из локального DFM…",window)
        private.setObjectName("actionLoadPrivateSourceDfmPictures")
        private.triggered.connect(self.choose_private_dfm)
        view_menu.addAction(private)
        self.private_action=private
        window.source_visual_skin=self

    def _source_style(self):
        self.root.setExpanding(False)
        self.root.setUsesScrollButtons(True)
        self.root.setIconSize(QSize(25,25))
        self.root.setStyleSheet(
            "QTabBar#Pages::tab { height:44px; min-width:91px;"
            " padding: 0px 7px; background:#f4f4f4;"
            " border:1px solid #b9b9b9; border-bottom:0px; }"
            "QTabBar#Pages::tab:selected { background:#ffffff;"
            " border-bottom:2px solid #ffffff; }"
            "QTabBar#Pages::tab:!selected:hover {background:#fafafa;}")
        window=self.window
        window.setFont(QFont("Tahoma",10))
        window.original_root_stack.setStyleSheet(
            "QStackedWidget#OriginalPageBodies {background:white;}")
        # Qt's hidden legacy tab/pane is not an additional source TPanel.
        window.tabs.setObjectName("OriginalLegacyClientPages")
        window.tabs.setStyleSheet(
            "QTabWidget#OriginalLegacyClientPages::pane {"
            " border:0px; margin:0px; padding:0px;}")
        window.task_subpages.setStyleSheet(
            "QTabWidget#taskSubpages::pane {"
            " border:0px; margin:0px; padding:0px;}")
        self.home.layout().setContentsMargins(0,0,0,0)
        self.home.layout().setSpacing(0)
        # Existing DSP meta row above taskSubpages has NO counterpart in
        # original PageStart and otherwise shifts five source controls.
        window.calc_source.hide()
        window.calc_status.hide()
        self.home.setProperty("sourcePageStartHasNoExtraTopPadding",True)
        self.start.host.setProperty("sourceViewFaithful",True)

    @staticmethod
    def _source_tasks_tab_icon():
        icon=QPixmap(24,24)
        icon.fill(Qt.transparent)
        painter=QPainter(icon)
        try:
            painter.setRenderHint(QPainter.Antialiasing,True)
            painter.setPen(QPen(QColor("#363636"),1.4))
            # Approximate black source task-pointer outline, not BWHand bytes.
            points=[QPoint(2,5),QPoint(8,9),QPoint(10,3),QPoint(13,5),
                    QPoint(13,10),QPoint(17,8),QPoint(20,11),
                    QPoint(20,17),QPoint(16,20),QPoint(10,17),QPoint(5,12)]
            for a,b in zip(points,points[1:]+points[:1]):
                painter.drawLine(a,b)
        finally:
            painter.end()
        return QIcon(icon)

    def _source_icons(self):
        style=self.window.style()
        for index,page in enumerate(ORIGINAL_ROOT_PAGES):
            standard=getattr(QStyle,_TAB_FALLBACK[page.object_name],
                             QStyle.SP_FileIcon)
            private_icon=self.start.host.private_task_icons.get("BWHand")
            original_tab=(page.object_name=="PageStart"
                          and private_icon is not None)
            self.root.setTabIcon(index,
                QIcon(private_icon) if original_tab
                else (self._source_tasks_tab_icon()
                      if page.object_name=="PageStart"
                      else style.standardIcon(standard)))
            self.root.setTabToolTip(index,
                f"Оригинальная страница {page.object_name}, "
                f"ImageName={page.image_name}; "
                + ("иконка загружена из локального DFM."
                   if original_tab else "значок Qt — приближение."))
        commands={}
        for name in _COMMAND_FALLBACK:
            widget=self.window.findChild(QWidget,name)
            # Source bSpecType/bSpecLines are real model QComboBoxes,
            # but presenters with distinct Qt names own the visible DFM
            # source canvas; never replace them with another control.
            if name=="bSpecType":
                widget=self.window.spec_type_button
            elif name=="bSpecLines":
                widget=self.window.spec_lines_button
            commands[name]=widget
        for name,widget in commands.items():
            if widget is None:
                raise ValueError("Missing source DFM visible command "+name)
            kind=getattr(QStyle,_COMMAND_FALLBACK[name],
                         QStyle.SP_FileIcon)
            icon=style.standardIcon(kind)
            widget.setIcon(icon)
            widget.setIconSize(QSize(22,22))
            if isinstance(widget,QToolButton):
                widget.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            widget.setProperty("sourceDfmImageCandidate",True)
            widget.setProperty("sourceOriginalBitmapProvided",False)

    def _configure_visibility(self,enabled:bool):
        enabled=bool(enabled)
        self.technical=enabled
        w=self.window
        w.menuBar().setVisible(enabled)
        w.statusBar().setVisible(enabled)
        w.note.setVisible(enabled)
        # F12 is a reversible entry into the compatible research workspace.
        # Closing it must restore the ACTUAL original window, not leave an
        # engineering dock, a secondary tab strip or the auxiliary toolbar
        # covering the native PaintBox and shifting its axis geometry.
        if not enabled:
            w.wave_inspector.hide()
            w.spec_inspector.hide()
            w.compat_toolbar.hide()
            w.research_tabs_action.setChecked(False)
            w.task_subpages.tabBar().hide()
        w.wave_advanced_button.setVisible(enabled)
        w.spec_advanced_button.setVisible(enabled)
        # The original pnView is 48px tall, not 64px. Its extra
        # provenance remains reachable in technical mode / tooltip.
        w.original_shell.view_context.setVisible(enabled)
        w.original_shell.view_panel.setFixedHeight(64 if enabled else 48)
        for item in self.start.technical_widgets:
            item.setVisible(enabled)
        # Qt-only PageStart header/note must not move source buttons
        # even if a user requests research tools through F12.
        for name in ("taskHomeHeading","taskSessionSummary",
                     "taskDeviceOfflineNotice"):
            widget=self.home.findChild(QWidget,name)
            if widget is not None:
                widget.hide()
        w.setProperty("sourceFaithfulWindowChrome",not enabled)
        w.setProperty("sourceTechnicalInterfaceVisible",enabled)
        self.update_runtime_tabs()
        # Runtime original pnMeasure has independent visible-state rules.
        # Re-evaluate the 53px panel when F12 changes between native
        # archive reading and compatible technical export controls.
        w.original_shell.measure_controls.render()
        if hasattr(self,"toggle_action"):
            self.toggle_action.setText(
                "Скрыть технический интерфейс Qt" if enabled else
                "Показать технический интерфейс Qt")

    def update_runtime_tabs(self):
        """Seven mounted TTabSheets, one/three actually visible in source UI.

        Technical F12 shows all. An explicitly selected hidden source mode
        is allowed to remain visible until the operator returns to Tasks
        or an archive page, keeping the original workspace accessible.
        """
        if self._visibility_guard:
            return self.root.currentIndex()
        ready=bool(self.window.tabs.isTabEnabled(1)
                   and self.window.tabs.isTabEnabled(2))
        current_index=self.root.currentIndex()
        page=(self.root.tabData(current_index)
              if current_index>=0 else "PageStart")
        if page is None:
            page="PageStart"
        expected=original_runtime_visible_pages(
            has_measurement=ready,technical=self.technical,
            current_page=page)
        self._visibility_guard=True
        try:
            for i in range(self.root.count()):
                self.root.setTabVisible(
                    i,self.root.tabData(i) in expected)
        finally:
            self._visibility_guard=False
        receipt=original_runtime_tab_contract(
            has_measurement=ready,technical=self.technical,
            current_page=page)
        self.root.setProperty("sourceRuntimeVisibilityReceipt",receipt)
        return current_index

    def reveal_page(self,index:int):
        """Explicit source task navigation without exposing all seven tabs."""
        if type(index) is not int or not 0<=index<self.root.count():
            raise ValueError("Original source page index outside DFM")
        if not self.root.isTabVisible(index):
            self.root.setTabVisible(index,True)
        self.root.setCurrentIndex(index)
        self.update_runtime_tabs()
        return self.root.tabData(index)

    def choose_private_dfm(self):
        path,_=QFileDialog.getOpenFileName(
            self.window,"Исходный mvkform.dfm — только локальное чтение",
            "","Delphi text DFM (*.dfm)")
        if not path:
            return False
        try:
            self.start.host.load_private_original_dfm(path)
            self.start.apply_private_icons()
            self._source_icons()
        except (OSError,ValueError) as exc:
            # Do not include the private filesystem path in any audit log.
            self.window.statusBar().showMessage(
                "Локальные TImage не распознаны: "+str(exc))
            return False
        self.window.statusBar().showMessage(
            "Локальные DFM изображения прочитаны: "
            + ("синий фон и " if self.start.host.private_blue_backgrounds_compatible
               else "сохранён голубой фон экрана; ")
            + ("оригинальные иконки и " if self.start.host.private_task_icons
               else "")
            + "логотип подключены без публикации.")
        return True

    def snapshot(self):
        """For offscreen DPI150 testing; no raw private bytes or paths."""
        return {
            "source":SOURCE,
            "root_pages":self.root.count(),
            "root_page_names":[
                self.root.tabData(i) for i in range(self.root.count())],
            "root_tabs_expand":self.root.expanding(),
            "root_tab_height":self.root.height(),
            "visible_source_tabs":[self.root.tabData(i)
                for i in range(self.root.count()) if self.root.isTabVisible(i)],
            "runtime_visibility":self.root.property(
                "sourceRuntimeVisibilityReceipt"),
            "start_logo_rect":_START_LOGO_RECT,
            "start_private_images_loaded":(
                self.start.host.original_pictures_loaded_privately),
            "start_private_icons_loaded":bool(
                self.start.host.private_task_icons),
            "start_private_background_palette_accepted":(
                self.start.host.private_blue_backgrounds_compatible),
            "technical":self.technical,
            "menu_visible":self.window.menuBar().isVisible(),
            "statusbar_visible":self.window.statusBar().isVisible(),
            "source_both_graphs_enabled":True,
            "source_fft_or_data_changed_by_skin":False,
            "original_image_pixel_parity_verified":False,
        }
