"""
plugin.py  --  ScriptBench main plugin class.
"""

from pathlib import Path
from typing import Any, Optional

from qgis.core import QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QTableWidgetItem

from .reporter import compute_derived, export_csv, export_html
from .runner import BenchmarkRunner, ScriptSummary
from .suite_manager import DEFAULT_SETTINGS, Suite, SuiteManager


def tr(message: str) -> str:
    return QCoreApplication.translate("ScriptBenchPlugin", message)


class ScriptBenchPlugin:
    PLUGIN_NAME = "ScriptBench"
    PLUGIN_TAG = "ScriptBench"

    def __init__(self, iface):
        self.iface = iface
        self._action: Optional[QAction] = None
        self._dialog = None
        self._suite_manager = SuiteManager()
        self._last_summaries: list[ScriptSummary] = []
        self._last_settings: dict[str, Any] = dict(DEFAULT_SETTINGS)

    # -----------------------------------------------------------------
    # Plugin lifecycle
    # -----------------------------------------------------------------

    def initGui(self):
        icon_path = Path(__file__).parent / "icons" / "scriptbench.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self._action = QAction(icon, self.PLUGIN_NAME, self.iface.mainWindow())
        self._action.setObjectName("scriptBenchAction")
        self._action.setToolTip(tr("Open ScriptBench — PyQGIS script benchmark tool"))
        self._action.setWhatsThis(
            tr(
                "ScriptBench runs PyQGIS scripts multiple times "
                "and produces detailed benchmark reports."
            )
        )
        self._action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self._action)
        self.iface.addPluginToMenu(self.PLUGIN_NAME, self._action)

    def unload(self):
        if self._action:
            self.iface.removePluginMenu(self.PLUGIN_NAME, self._action)
            self.iface.removeToolBarIcon(self._action)
            self._action = None
        if self._dialog:
            self._dialog.close()
            self._dialog = None

    # -----------------------------------------------------------------
    # Dialog lifecycle
    # -----------------------------------------------------------------

    def run(self):
        from .ui.dialog import load_dialog

        if self._dialog is None:
            self._dialog = load_dialog(self.iface.mainWindow())
            self._connect_signals()
            self._populate_suites()
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _connect_signals(self):
        d = self._dialog
        d.btnBrowse.clicked.connect(self._browse_folder)
        d.btnRefreshScripts.clicked.connect(self._refresh_scripts)
        d.btnRun.clicked.connect(self._start_run)
        d.btnCancel.clicked.connect(self._cancel_run)
        d.btnSaveSuite.clicked.connect(self._save_suite)
        d.btnDeleteSuite.clicked.connect(self._delete_suite)
        d.cmbSuite.currentIndexChanged.connect(self._load_suite)
        d.btnExportCSV.clicked.connect(self._export_csv)
        d.btnExportHTML.clicked.connect(self._export_html)
        d.btnClearLog.clicked.connect(d.txtLog.clear)
        d.btnClose.clicked.connect(d.hide)

    # -----------------------------------------------------------------
    # Suite management
    # -----------------------------------------------------------------

    def _populate_suites(self):
        d = self._dialog
        d.cmbSuite.blockSignals(True)
        d.cmbSuite.clear()
        d.cmbSuite.addItem("")
        for name in self._suite_manager.list_suites():
            d.cmbSuite.addItem(name)
        d.cmbSuite.blockSignals(False)

    def _load_suite(self, _index=None):
        d = self._dialog
        name = d.cmbSuite.currentText().strip()
        if not name:
            return
        suite = self._suite_manager.load(name)
        if suite is None:
            return
        d.txtFolder.setText(suite.folder)
        d.txtFilter.setText(suite.settings.get("file_filter", "*.py"))
        d.txtDescription.setText(suite.description)
        d.spnRepeats.setValue(suite.settings.get("repeats", 5))
        d.spnWarmups.setValue(suite.settings.get("warmups", 1))
        d.chkSaveOutput.setChecked(suite.settings.get("save_output", False))
        d.chkPreserveTemp.setChecked(suite.settings.get("preserve_temp", False))
        d.chkProfile.setChecked(suite.settings.get("profile_runs", False))
        self._refresh_scripts()

    def _save_suite(self):
        d = self._dialog
        name = d.cmbSuite.currentText().strip()
        if not name:
            QMessageBox.warning(
                d, self.PLUGIN_NAME, tr("Enter a suite name before saving.")
            )
            return
        suite = Suite(
            name=name,
            folder=d.txtFolder.text().strip(),
            settings={
                "repeats": d.spnRepeats.value(),
                "warmups": d.spnWarmups.value(),
                "save_output": d.chkSaveOutput.isChecked(),
                "preserve_temp": d.chkPreserveTemp.isChecked(),
                "profile_runs": d.chkProfile.isChecked(),
                "file_filter": d.txtFilter.text().strip() or "*.py",
            },
            description=d.txtDescription.text().strip(),
        )
        self._suite_manager.save(suite)
        self._populate_suites()
        idx = d.cmbSuite.findText(name)
        if idx >= 0:
            d.cmbSuite.blockSignals(True)
            d.cmbSuite.setCurrentIndex(idx)
            d.cmbSuite.blockSignals(False)
        self._log(tr("Suite saved: {0}").format(name))

    def _delete_suite(self):
        d = self._dialog
        name = d.cmbSuite.currentText().strip()
        if not name:
            return
        reply = QMessageBox.question(
            d,
            self.PLUGIN_NAME,
            tr("Delete suite '{0}'?").format(name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._suite_manager.delete(name)
            self._populate_suites()
            self._log(tr("Suite deleted: {0}").format(name))

    # -----------------------------------------------------------------
    # Script browsing
    # -----------------------------------------------------------------

    def _browse_folder(self):
        d = self._dialog
        folder = QFileDialog.getExistingDirectory(
            d, tr("Select script folder"), d.txtFolder.text() or ""
        )
        if folder:
            d.txtFolder.setText(folder)
            self._refresh_scripts()

    def _refresh_scripts(self):
        d = self._dialog
        d.lstScripts.clear()
        folder = d.txtFolder.text().strip()
        filt = d.txtFilter.text().strip() or "*.py"
        if not folder or not Path(folder).is_dir():
            d.lstScripts.addItem(tr("(folder not found)"))
            return
        scripts = sorted(Path(folder).glob(filt))
        scripts = [p for p in scripts if p.is_file()]
        if not scripts:
            d.lstScripts.addItem(tr("(no matching files)"))
        for p in scripts:
            d.lstScripts.addItem(p.name)

    # -----------------------------------------------------------------
    # Benchmark execution
    # -----------------------------------------------------------------

    def _build_settings(self) -> dict[str, Any]:
        d = self._dialog
        return {
            "repeats": d.spnRepeats.value(),
            "warmups": d.spnWarmups.value(),
            "save_output": d.chkSaveOutput.isChecked(),
            "preserve_temp": d.chkPreserveTemp.isChecked(),
            "profile_runs": d.chkProfile.isChecked(),
            "file_filter": d.txtFilter.text().strip() or "*.py",
        }

    def _start_run(self):
        d = self._dialog
        folder = d.txtFolder.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(
                d, self.PLUGIN_NAME, tr("Select a valid script folder first.")
            )
            return
        settings = self._build_settings()
        script_paths = sorted(
            str(p) for p in Path(folder).glob(settings["file_filter"]) if p.is_file()
        )
        if not script_paths:
            QMessageBox.warning(
                d, self.PLUGIN_NAME, tr("No scripts found matching the filter.")
            )
            return

        self._log(
            tr("Starting benchmark: {0} scripts, {1} repeats, {2} warm-ups").format(
                len(script_paths), settings["repeats"], settings["warmups"]
            )
        )
        self._last_settings = settings
        self._last_summaries = []

        d.btnRun.setEnabled(False)
        d.btnCancel.setEnabled(False)
        d.progressBar.setRange(0, 0)
        d.lblStatus.setText(tr("Running on main QGIS thread..."))
        d.tabWidget.setCurrentIndex(2)

        try:
            runner = BenchmarkRunner(progress_callback=self._on_progress)
            summaries = runner.run_suite(
                script_paths=script_paths,
                repeats=settings["repeats"],
                warmups=settings["warmups"],
                save_output=settings["save_output"],
                profile_runs=settings["profile_runs"],
                preserve_temp=settings["preserve_temp"],
            )
            self._on_finished(summaries)
        except Exception:
            import traceback

            self._on_error(traceback.format_exc())
        finally:
            self._cleanup_thread()

    def _cancel_run(self):
        self._log(
            tr(
                "Cancel is disabled in safe mode because QGIS Processing "
                "runs on the main thread."
            )
        )

    def _cleanup_thread(self):
        d = self._dialog
        d.btnRun.setEnabled(True)
        d.btnCancel.setEnabled(False)
        d.progressBar.setRange(0, 100)
        d.progressBar.setValue(100)

    def _on_progress(self, msg: str):
        self._log(msg)
        self._dialog.lblStatus.setText(msg)
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

    def _on_finished(self, summaries: list[ScriptSummary]):
        self._last_summaries = summaries
        self._log(
            tr("Benchmark complete. {0} scripts evaluated.").format(len(summaries))
        )
        self._dialog.lblStatus.setText(tr("Done."))
        self._populate_results_table(summaries)
        self._dialog.tabWidget.setCurrentIndex(1)

    def _on_error(self, msg: str):
        self._log(tr("ERROR: {0}").format(msg))
        self._dialog.lblStatus.setText(tr("Error — see log."))
        QgsMessageLog.logMessage(msg, self.PLUGIN_TAG, level=2)
        QMessageBox.critical(
            self._dialog,
            tr("ScriptBench error"),
            tr(
                "Benchmark failed. If this happened during Processing execution, "
                "the most likely cause is that QGIS/GDAL code was run from a worker "
                "thread in the previous plugin build, or one of the scripts passed "
                "an invalid layer/parameter combination.\n\n{0}"
            ).format(msg[:1200]),
        )

    # -----------------------------------------------------------------
    # Results table
    # -----------------------------------------------------------------

    RESULT_COLUMNS: list[list[str]] = [
        (tr("Script"), "script_name"),
        (tr("Mean (s)"), None),
        (tr("Min (s)"), None),
        (tr("Median (s)"), None),
        (tr("Stdev (s)"), None),
        (tr("CV (%)"), None),
        (tr("Compute (s)"), None),
        (tr("Save (s)"), None),
        (tr("Slowdown"), None),
        (tr("Fail/Runs"), None),
        (tr("Phases"), None),
    ]

    def _populate_results_table(self, summaries: list[ScriptSummary]):
        rows = compute_derived(summaries)
        d = self._dialog
        tbl = d.tblResults
        tbl.setRowCount(len(rows))
        tbl.setColumnCount(len(self.RESULT_COLUMNS))
        tbl.setHorizontalHeaderLabels([c[0] for c in self.RESULT_COLUMNS])

        def _cell(val, cell_fmt=".3f"):
            if val is None:
                return QTableWidgetItem("—")
            if isinstance(val, float):
                item = QTableWidgetItem(f"{val:{cell_fmt}}")
                item.setData(Qt.ItemDataRole.UserRole, val)
                return item
            return QTableWidgetItem(str(val))

        for ri, row in enumerate(rows):
            tbl.setItem(ri, 0, _cell(row["script"]))
            tbl.setItem(ri, 1, _cell(row["wall_mean"]))
            tbl.setItem(ri, 2, _cell(row["wall_min"]))
            tbl.setItem(ri, 3, _cell(row["wall_median"]))
            tbl.setItem(ri, 4, _cell(row["wall_stdev"]))
            tbl.setItem(ri, 5, _cell(row["wall_cv"], ".1f"))
            tbl.setItem(ri, 6, _cell(row["compute_mean"]))
            tbl.setItem(ri, 7, _cell(row["save_mean"]))
            sp = row["speedup_vs_fastest"]
            tbl.setItem(
                ri,
                8,
                _cell(sp, ".2f") if sp is not None else QTableWidgetItem("—"),
            )
            tbl.setItem(ri, 9, _cell(f"{row['failures']}/{row['runs']}"))
            tbl.setItem(ri, 10, _cell(tr("yes") if row["has_phases"] else tr("no")))

        tbl.resizeColumnsToContents()

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------

    def _export_csv(self):
        if not self._last_summaries:
            QMessageBox.information(
                self._dialog, self.PLUGIN_NAME, tr("Run a benchmark first.")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self._dialog, tr("Export CSV"), "", tr("CSV files (*.csv)")
        )
        if not path:
            return
        try:
            export_csv(self._last_summaries, path)
            self._log(tr("CSV exported: {0}").format(path))
        except Exception as exc:
            QMessageBox.critical(self._dialog, tr("Export error"), str(exc))

    def _export_html(self):
        if not self._last_summaries:
            QMessageBox.information(
                self._dialog, self.PLUGIN_NAME, tr("Run a benchmark first.")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self._dialog, tr("Export HTML report"), "", tr("HTML files (*.html)")
        )
        if not path:
            return
        try:
            suite_name = self._dialog.cmbSuite.currentText().strip()
            export_html(
                self._last_summaries,
                path,
                suite_name=suite_name,
                repeats=self._last_settings.get("repeats", 0),
                warmups=self._last_settings.get("warmups", 0),
            )
            self._log(tr("HTML report exported: {0}").format(path))
        except Exception as exc:
            QMessageBox.critical(self._dialog, tr("Export error"), str(exc))

    # -----------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------

    def _log(self, msg: str):
        self._dialog.txtLog.appendPlainText(msg)
        QgsMessageLog.logMessage(msg, self.PLUGIN_TAG, level=0)
