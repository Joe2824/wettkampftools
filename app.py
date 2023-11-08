import sys
import os
import importlib
import datetime
import platform
import pandas as pd
from PyQt6.QtCore import QUrl, QSettings
from PyQt6.QtGui import QIcon, QDesktopServices, QPainter, QColor, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QHBoxLayout, QGroupBox, QSizePolicy, QLineEdit, QFileDialog, QMessageBox, QListWidget, QCheckBox, QListWidgetItem, QSpacerItem, QComboBox, QFormLayout, QTabWidget

basedir = os.path.dirname(__file__)

try:
    from ctypes import windll  # Only exists on Windows.
    APPID = 'joe2824.wettkampftools'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(APPID)
except ImportError:
    pass

if '_PYIBoot_SPLASH' in os.environ and importlib.util.find_spec("pyi_splash"):
    import pyi_splash
    pyi_splash.update_text('Loading...')
    pyi_splash.close()


if  importlib.util.find_spec("win32com"):
    from win32com.client import *
    def get_version_number(file_path):
        information_parser = Dispatch("Scripting.FileSystemObject")
        print(information_parser)
        version = information_parser.GetFileVersion(file_path)
        return version
    VERSION = f'v{get_version_number(sys.argv[0])}'
else:
    VERSION = 'DEV VERSION'


class MainApplication(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f'Wettkampftools {VERSION}')
        self.setGeometry(100, 100, 1000, 600)

        # Hauptwidget mit horizontalem Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Seitenwechsel-Widget für die Hauptanwendungen
        self.stacked_widget = QStackedWidget()
        central_layout = QHBoxLayout()
        central_layout.addWidget(self.setup_navigation())
        central_layout.addWidget(self.stacked_widget)
        central_widget.setLayout(central_layout)

        # Inhalte für die Hauptanwendungen hinzufügen
        self.setup_wwk_preperation()
        self.setup_wwk_evaluation()
        self.setup_tools_group()
        self.setup_settings_page()

        self.load_settings()

    def setup_navigation(self):
        # Links angeordnete Navigationsliste
        navigation_widget = QWidget()
        navigation_widget.setMaximumWidth(230)
        navigation_layout = QVBoxLayout()

        logo = QLabel()
        pixmap = QPixmap(os.path.join(basedir,'images','logo.png') )
        logo.setPixmap(pixmap)
        navigation_layout.addWidget(logo)

        top_groups = QVBoxLayout()
        top_groups.setSpacing(30)
        # Gruppe "Wellenwettkampf" mit Buttons "Vorbereitung" und "Auswertung"
        waves_group = QGroupBox("Wellenwettkampf")
        waves_group.setFixedHeight(180)
        waves_layout = QVBoxLayout()
        waves_layout.addWidget(QPushButton("Vorbereitung", clicked=lambda: self.change_page(0)))
        waves_layout.addWidget(QPushButton("Auswertung", clicked=lambda: self.change_page(1)))
        waves_group.setLayout(waves_layout)
        top_groups.addWidget(waves_group)

        # Gruppe "Tools" mit Button "Urkunden sortieren"
        tools_group = QGroupBox("Tools")
        tools_group.setFixedHeight(80)
        tools_layout = QVBoxLayout()
        tools_layout.addWidget(QPushButton("Urkunden sortieren", clicked=lambda: self.change_page(2)))
        tools_group.setLayout(tools_layout)
        top_groups.addWidget(tools_group)

        top_groups.addStretch()

        navigation_layout.addLayout(top_groups)

        bottom_navigation = QHBoxLayout()

        bottom_navigation.addWidget(QPushButton("Einstellungen", clicked=lambda: self.change_page(3)))
        bottom_navigation.addWidget(QPushButton("Info", clicked=lambda: self.msg_box('Info', f'Version: {VERSION.replace("v", "")}\nAuthor: Joel Klein\nGithub: https://github.com/joe2824/wettkampftools')))

        navigation_layout.addLayout(bottom_navigation)

        navigation_widget.setLayout(navigation_layout)
        return navigation_widget

    def msg_box(self, title, text, icon: QMessageBox.Icon=QMessageBox.Icon.Information, buttonText=None, buttonClick=None):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(icon)
        msg_box.setText(text)
        msg_box.addButton(QMessageBox.StandardButton.Ok)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        if buttonText and buttonClick:
            custom_button = msg_box.addButton(buttonText, QMessageBox.ButtonRole.ActionRole)
            custom_button.clicked.connect(buttonClick)
        msg_box.exec()

    def change_page(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def create_listwidget(self):
        listwidget = QListWidget()
        listwidget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        listwidget.setAcceptDrops(True)
        return listwidget

    def select_isc_export_file(self):
        self.isc_export_file_path, _ = QFileDialog.getOpenFileName(self, 'ISC Export auswählen','','ISC Export (*.csv)')
        if self.isc_export_file_path:
            self.isc_export_file_entry.setText(self.isc_export_file_path)
            self.generate_competition_preperation()

    def generate_competition_preperation(self):
        file = self.isc_export_file_path

        if not os.path.exists(file):
            self.msg_box(title='Fehler!', text=f'{file}˙\nexistiert nicht!', icon=QMessageBox.Icon.Critical)
            return

        # Check for Excel file
        if not file.endswith(('.csv')):
            self.msg_box(title='Fehler!', text=f'{file}˙\ist keine CSV Datei!', icon=QMessageBox.Icon.Critical)
            return
        
        try:

            # Prepair Data and add Team Numbers if multiple Teams in one AK exist.
            df = pd.read_csv(file, sep=';', encoding='latin-1')
            # Remove Unnamed columns
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            # Remove unessesary whitespaces
            df['gliederung'] = df['gliederung'].str.strip()
            df['ak'] = df['ak'].str.replace(r'\bAK\b', 'AK', case=False, regex=True)

            # Count teams from same organization, age group and gender
            df['ctn'] = df.groupby(['gliederung', 'ak', 'geschlecht'])['gliederung'].transform('count')
            df['cc'] = df.groupby(['gliederung', 'ak', 'geschlecht'])['gliederung'].cumcount(ascending=False)
            # Concat team name
            df['name'] = df.apply(lambda x: x["gliederung"] if x["ctn"] < 2 else f'{x["gliederung"]} {x["ctn"] - x["cc"]}', axis=1)
            # Remove temporary columns
            df.drop(columns=['ctn', 'cc'], inplace=True)

            df.replace('AK offen', 'AK Offen', inplace=True)

            if self.simplify_senior_groups:
                df.replace(self.age_groups_senior_team, 'AK Senioren', inplace=True)

            # Preselect AK that are allowed to start in wave
            df['start_as_akw'] = df['ak'].str.upper().isin(ak.upper() for ak in self.age_groups_start_permit_wwk[self.age_groups_start_permit_wwk.index(self.start_age_group_wwk):])
            
            self.preperation_competition_df = df

            self.gliederungen_list.clear()
            self.gliederungen_list.addItems(df['gliederung'].unique())
            self.gliederungen_list.show()
            self.teams_list.show()
            self.reset_selected_teams.show()
            self.export_preperation_file.show()

        except Exception as e:
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Fehler')
            msg_box.setText(f'Ist die Datei\n{file}˙\nein Export aus dem ISC?\nVerwende bitte eine andere Datei!\n{e}')
            msg_box.addButton(QMessageBox.StandardButton.Ok)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.exec()
            return

    def show_gliederung_teams(self):
        df = self.preperation_competition_df

        selected_gliederung = self.gliederungen_list.currentItem().text()
        filtered_df = df[df['gliederung'] == selected_gliederung]

        self.teams_list.clear()
        for index, team in filtered_df[['name', 'ak', 'geschlecht', 'start_as_akw']].to_dict('index').items():
            item = QListWidgetItem(self.teams_list)
            name = f"{team['name']} {team['ak']} {team['geschlecht']}"
            checkbox = QCheckBox(name)
            item.setSizeHint(checkbox.sizeHint())
            self.teams_list.setItemWidget(item, checkbox)
            checkbox.setChecked(team['start_as_akw'])
            checkbox.stateChanged.connect(lambda state, index=index, checkbox=checkbox: self.update_preperation_competition_state(index, checkbox.isChecked()))
    
    def update_preperation_competition_state(self, index, state):
        self.preperation_competition_df.at[index, 'start_as_akw'] = state

    def export_competition_preperation(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Export F:xile', f'{str(datetime.datetime.now().date()).replace("-","")}_WWK_Meldungen', 'Excel files (*.xlsx)')
        df = self.preperation_competition_df

        filtered_df = df[df['start_as_akw']]
        filtered_df['ak'] = filtered_df['ak'].str.replace(r'\bAK\b', 'AkW', case=False, regex=True)

        result_df = pd.concat([df, filtered_df])

        # Reset the index of the result DataFrame
        result_df.reset_index(drop=True, inplace=True)
        result_df.drop(['start_as_akw'], axis=1, inplace=True)

        # Predefine category sort
        result_df['ak'] = pd.Categorical(result_df['ak'], self.all_age_groups)
        # Sort values
        result_df.sort_values(by=['ak', 'geschlecht', 'gliederung'], ascending=[True, False, False], inplace=True)

        if file_path:
            result_df.to_excel(file_path, sheet_name='Meldungen', index=False)
            self.msg_box(title='Export erfolgreich!', text='Export erfolgreich!', icon=QMessageBox.Icon.Information, buttonText='Meldungen öffnen', buttonClick=lambda _, path=file_path: self.open_export_file(path))

    def open_export_file(self, path):
        url = QUrl.fromLocalFile(path)
        QDesktopServices.openUrl(url)

    def setup_wwk_preperation(self):
        self.isc_export_file_path = None

        # Seite für "Wellenwettkampf" mit Inhalt
        wwk_preperation = QWidget()
        wwk_preperation_layout = QVBoxLayout()

        # Label at the top
        label = QLabel("Wellenwettkampf Vorbereitung")
        label.setStyleSheet("font-size: 24pt;")  # Set font size to 24pt
        wwk_preperation_layout.addWidget(label)

        # BoxLayout Measurments Folder selection
        select_isc_file_layout = QHBoxLayout()
        wwk_preperation_layout.addLayout(select_isc_file_layout)

        folder_label_preperation = QLabel('ISC Export:')
        select_isc_file_layout.addWidget(folder_label_preperation)

        self.isc_export_file_entry = QLineEdit()
        select_isc_file_layout.addWidget(self.isc_export_file_entry)

        self.folder_button_preperation = QPushButton('Auswählen', clicked=self.select_isc_export_file) # type: ignore
        select_isc_file_layout.addWidget(self.folder_button_preperation)
    
        select_gliederung_layout = QVBoxLayout()
        wwk_preperation_layout.addLayout(select_gliederung_layout)

        select_gliederung_teams_layout = QHBoxLayout()
        select_gliederung_layout.addLayout(select_gliederung_teams_layout)

        select_gliederung_teams_buttons = QHBoxLayout()
        select_gliederung_layout.addLayout(select_gliederung_teams_buttons)

        self.gliederungen_list = QListWidget()
        self.gliederungen_list.itemSelectionChanged.connect(self.show_gliederung_teams)
        self.gliederungen_list.hide()
        select_gliederung_teams_layout.addWidget(self.gliederungen_list)

        # Create a QListWidget to display names with checkboxes
        self.teams_list = QListWidget()
        self.teams_list.hide()
        select_gliederung_teams_layout.addWidget(self.teams_list)

        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        select_gliederung_teams_buttons.addSpacerItem(spacer)

        self.reset_selected_teams = QPushButton('Auswahl zurücksetzten', clicked=self.generate_competition_preperation) # type: ignore
        self.reset_selected_teams.hide()
        select_gliederung_teams_buttons.addWidget(self.reset_selected_teams)

        self.export_preperation_file = QPushButton('Exportieren', clicked=self.export_competition_preperation) # type: ignore
        self.export_preperation_file.hide()
        wwk_preperation_layout.addWidget(self.export_preperation_file)

        wwk_preperation_layout.addStretch()

        wwk_preperation.setLayout(wwk_preperation_layout)
        self.stacked_widget.addWidget(wwk_preperation)

    def creation_date(self, path_to_file):
        '''
        Try to get the date that a file was created, falling back to when it was
        last modified if that isn't possible.
        See http://stackoverflow.com/a/39501288/1709587 for explanation.
        '''
        if platform.system() == 'Windows':
            return os.path.getctime(path_to_file)
        else:
            stat = os.stat(path_to_file)
            try:
                return stat.st_birthtime
            except AttributeError:
                # We're probably on Linux. No easy way to get creation dates here,
                # so we'll settle for when its content was last modified.
                return stat.st_mtime

    def evaluation_wwk(self, evaluate=True):
        file = self.jauswertung_file_path

        if not os.path.exists(file):
            self.msg_box(title='Fehler', text=f'{file}˙\nexistiert nicht!', icon=QMessageBox.Icon.Critical)
            return

        # Check for Excel file
        if not file.endswith(('.xls', '.xlsx')):
            self.msg_box(title='Fehler', text=f'{file}˙\ist keine Excel Datei!', icon=QMessageBox.Icon.Critical)
            return
        
        try:
            file_year = datetime.date.fromtimestamp(self.creation_date(file)).year
            current_year = datetime.date.today().year
            if file_year != current_year:
                self.msg_box(title='ACHTUNG!', text=f'Hast du die richtige Datei ausgewählt?\nDie Datei ist aus dem Jahr {file_year}', icon=QMessageBox.Icon.Critical)

            seriendruck = pd.read_excel(file, sheet_name='Seriendruck')

            # Fix names when something is wrong
            seriendruck['Altersklasse'].replace(r'\bAK\b', value='AK', regex=True, inplace=True)
            seriendruck['Altersklasse'].replace(r'\bAkW\b', value='AkW', regex=True, inplace=True)
            seriendruck.replace('AK offen', 'AK Offen', inplace=True)
            seriendruck.replace('AkW offen', 'AkW Offen', inplace=True)

            seriendruck['WWK'] = seriendruck['Altersklasse'].str.contains(r'\bAkW\b', case=False, na=False).replace({True: 'x', False: ''}, regex=True)

            # Predefine category sort
            seriendruck['Altersklasse'] = pd.Categorical(seriendruck['Altersklasse'], categories=self.all_age_groups)
            # Sort values
            seriendruck.sort_values(by=['Altersklasse', 'Geschlecht', 'Platz'], ascending=[True, False, False], inplace=True)

            filename = f'{str(datetime.datetime.now().date()).replace("-","")}_Seriendruck'

            if evaluate:
                filename = f'{str(datetime.datetime.now().date()).replace("-","")}_WWK_Auswertung'
                df = pd.read_excel(file, sheet_name='Daten')

                if self.drop_not_started_teams:
                    df = df.dropna(subset=['Platz'])

                df['Punktzahl'] = df.groupby(['Altersklasse', 'Geschlecht'])['Platz'].transform(lambda x: len(x) + 1 - x)
                df['Punktzahl'] = df.apply(lambda row: row['Punktzahl'] + 1 if row['Platz'] == 1 else row['Punktzahl'], axis=1)

                df_AK = df[df['Altersklasse'].str.contains(r'\bAK\b')]
                df_AkW = df[df['Altersklasse'].str.contains(r'\bAkW\b')]

                ergebnis = df_AK.groupby('Gliederung')['Punktzahl'].sum().reset_index().sort_values(by='Punktzahl', ascending=False).reset_index(drop=True)
                ergebnis.index += 1

                ergebnis_welle = df_AkW.groupby('Gliederung')['Punktzahl'].sum().reset_index().sort_values(by='Punktzahl', ascending=False).reset_index(drop=True)
                ergebnis_welle.index += 1

            output_path, _ = QFileDialog.getSaveFileName(self, 'Speichern', filename, 'Auswertung Export (*.xlsx)')
            if output_path:
                with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                    seriendruck.to_excel(writer, sheet_name='Seriendruck', index=False)
                    if evaluate:
                        ergebnis.to_excel(writer, sheet_name='Rettungswettkampf', index=True)
                        ergebnis_welle.to_excel(writer, sheet_name='Wellenwettkampf', index=True)
                        df.to_excel(writer, sheet_name='Quelldaten', index=False)
                
                self.msg_box(title='Export erfolgreich!', text='Export erfolgreich!', icon=QMessageBox.Icon.Information, buttonText='Auswertung öffnen', buttonClick=lambda _, path=output_path: self.open_export_file(path))

        except Exception as e:
            self.msg_box(title='Fehler', text=f'Ist die Datei\n{file}˙\nein Export aus JAuswertung?\nVerwende bitte eine andere Datei!\n{e}', icon=QMessageBox.Icon.Critical)
            return

    def select_jauswertung_export_file(self, evaluate=True):
        self.jauswertung_file_path, _ = QFileDialog.getOpenFileName(self, 'JAuswertung Export auswählen','','JAuswertung Export (*.xls *.xlsx)')
        if self.jauswertung_file_path:
            self.jauswertung_file_entry.setText(self.jauswertung_file_path)
            self.evaluation_wwk(evaluate)

    def setup_wwk_evaluation(self):
        self.jauswertung_file_path = None
        # Seite für "Wellenwettkampf" mit Inhalt
        wwk_evaluation = QWidget()
        wwk_evaluation_layout = QVBoxLayout()
        label = QLabel("Wellenwettkampf Auswertung")
        label.setStyleSheet("font-size: 24pt;")  # Set font size to 24pt
        wwk_evaluation_layout.addWidget(label)

         # BoxLayout Measurments Folder selection
        select_jauswertung_file_layout = QHBoxLayout()
        wwk_evaluation_layout.addLayout(select_jauswertung_file_layout)

        folder_label_evaluation = QLabel('JAuswertung Export:')
        select_jauswertung_file_layout.addWidget(folder_label_evaluation)

        self.jauswertung_file_entry = QLineEdit()
        select_jauswertung_file_layout.addWidget(self.jauswertung_file_entry)

        self.folder_button_evaluation = QPushButton('Auswählen', clicked=lambda: self.select_jauswertung_export_file(True)) # type: ignore
        select_jauswertung_file_layout.addWidget(self.folder_button_evaluation)

        wwk_evaluation_layout.addStretch()
        wwk_evaluation.setLayout(wwk_evaluation_layout)
        self.stacked_widget.addWidget(wwk_evaluation)

    def setup_tools_group(self):
        # Seite für "Tools" mit Inhalt
        tools_page = QWidget()
        tools_layout = QVBoxLayout()
        label = QLabel("Urkunden sortieren")
        label.setStyleSheet("font-size: 24pt;")  # Set font size to 24pt
        tools_layout.addWidget(label)

         # BoxLayout Measurments Folder selection
        select_jauswertung_file_layout = QHBoxLayout()
        tools_layout.addLayout(select_jauswertung_file_layout)

        select_jauswertung_file_layout.addWidget(QLabel('JAuswertung Export:'))

        self.jauswertung_file_entry = QLineEdit()
        select_jauswertung_file_layout.addWidget(self.jauswertung_file_entry)

        self.folder_button_evaluation = QPushButton('Auswählen', clicked=lambda: self.select_jauswertung_export_file(False)) # type: ignore
        select_jauswertung_file_layout.addWidget(self.folder_button_evaluation)

        tools_layout.addStretch()
        tools_page.setLayout(tools_layout)
        self.stacked_widget.addWidget(tools_page)
     
    def add_age_group(self, input_field : QLineEdit, listwidget: QListWidget, combobox: QComboBox = None):
        input = input_field.text()
        if input:
            listwidget.addItem(input)
            input_field.clear()
            
            if combobox:
                combobox.addItem(input)
        
    def delete_age_group(self, listwidget: QListWidget, combobox: QComboBox = None):
        selected_items = listwidget.selectedItems()

        if selected_items:
            for item in selected_items:
                listwidget.takeItem(listwidget.row(item))

                if combobox and item.text() in [combobox.itemText(i) for i in range(combobox.count())]:
                    combobox.removeItem(combobox.findText(item.text()))

    def load_settings(self):
        self.settings = QSettings("Joe2824", "WettkampfTools")

        self.age_groups_listwidget.clear()
        self.age_groups = self.settings.value("age_groups", ['AK 10', 'AK 12', 'AK 13/14', 'AK 15/16', 'AK 17/18', 'AK Offen'])
        self.age_groups_listwidget.addItems(self.age_groups)

        self.age_groups_senior_team_listwidget.clear()
        self.age_groups_senior_team = self.settings.value("age_groups_senior_team", ['AK 100', 'AK 120', 'AK 140', 'AK 170', 'AK 200', 'AK 240', 'AK 280+'])
        self.age_groups_senior_team_listwidget.addItems(self.age_groups_senior_team)

        self.age_groups_senior_individual_listwidget.clear()
        self.age_groups_senior_individual = self.settings.value("age_groups_senior_individual", ['AK 25', 'AK 30', 'AK 35', 'AK 40', 'AK 45', 'AK 50', 'AK 55', 'AK 60+'])
        self.age_groups_senior_individual_listwidget.addItems(self.age_groups_senior_individual)

        self.start_ak_wwk_combobox.clear()
        self.start_ak_wwk_combobox.addItems(self.age_groups)   
        self.start_age_group_wwk = self.settings.value("start_age_group_wwk", 'AK 13/14')
        self.start_ak_wwk_combobox.setCurrentText(self.start_age_group_wwk)

        self.simplify_senior_groups = self.settings.value("simplify_senior_groups", True, type=bool)
        self.simplify_senior_groups_checkbox.setChecked(self.simplify_senior_groups)

        self.drop_not_started_teams = self.settings.value("drop_not_started_teams", True, type=bool)
        self.drop_not_started_teams_checkbox.setChecked(self.drop_not_started_teams)
        
        self.age_groups_wwk = self.age_groups + ['AK Senioren'] if self.simplify_senior_groups else self.age_groups + self.age_groups_senior_team
        self.age_groups_start_permit_wwk = [ak for ak in self.age_groups_wwk if ak >= self.start_age_group_wwk]

        self.age_groups_wwk = [group.replace('AK', 'AkW') for group in self.age_groups_start_permit_wwk]

        self.all_age_groups = self.age_groups + self.age_groups_senior_individual + self.age_groups_senior_team + ['AK Senioren'] + self.age_groups_wwk            

    def restore_settings(self):
        # Restore default values for age_groups
        default_age_groups = ['AK 10', 'AK 12', 'AK 13/14', 'AK 15/16', 'AK 17/18', 'AK Offen']
        self.age_groups_listwidget.clear()
        self.age_groups_listwidget.addItems(default_age_groups)
        # Restore default values for age_groups_senior_team
        default_age_groups_senior_team = ['AK 100', 'AK 120', 'AK 140', 'AK 170', 'AK 200', 'AK 240', 'AK 280+']
        self.age_groups_senior_team_listwidget.clear()
        self.age_groups_senior_team_listwidget.addItems(default_age_groups_senior_team)
        # Restore default values for age_groups_senior_individual
        default_age_groups_senior_individual = ['AK 25', 'AK 30', 'AK 35', 'AK 40', 'AK 45', 'AK 50', 'AK 55', 'AK 60+']
        self.age_groups_senior_individual_listwidget.clear()
        self.age_groups_senior_individual_listwidget.addItems(default_age_groups_senior_individual)
        
        # Restore default value for start_ak_wwk
        self.start_ak_wwk_combobox.clear()
        self.start_ak_wwk_combobox.addItems(default_age_groups)
        self.start_ak_wwk_combobox.setCurrentText('AK 13/14')

        self.simplify_senior_groups = True
        self.simplify_senior_groups_checkbox.setChecked(self.simplify_senior_groups)

        self.drop_not_started_teams = True
        self.drop_not_started_teams_checkbox.setChecked(self.drop_not_started_teams)

        QMessageBox.information(self, "Einstellungen wiederhergestellt", "Alle Einstellungen zurückgesetzt.\nSpeichern nicht vergessen.")
        
    def save_settings(self):
        # Get age groups from QListWidget
        age_groups = [self.age_groups_listwidget.item(i).text() for i in range(self.age_groups_listwidget.count())]
        age_groups_senior_team = [self.age_groups_senior_team_listwidget.item(i).text() for i in range(self.age_groups_senior_team_listwidget.count())]
        age_groups_senior_individual = [self.age_groups_senior_individual_listwidget.item(i).text() for i in range(self.age_groups_senior_individual_listwidget.count())]
                
        # Save settings to QSettings
        self.settings.setValue("age_groups", age_groups)
        self.settings.setValue("age_groups_senior_team", age_groups_senior_team)
        self.settings.setValue("age_groups_senior_individual", age_groups_senior_individual)
        self.settings.setValue("start_age_group_wwk", self.start_ak_wwk_combobox.currentText())
        self.settings.setValue("simplify_senior_groups", self.simplify_senior_groups_checkbox.isChecked())
        self.settings.setValue("drop_not_started_teams", self.drop_not_started_teams_checkbox.isChecked())
        
        # Display a confirmation message
        QMessageBox.information(self, "Einstellungen speichern", "Einstellungen erfolgreich gespeichert!!")

        self.load_settings()

    def setup_settings_page(self):
        # Seite für "Einstellungen" mit Inhalt
        settings_page = QWidget()
        settings_layout = QVBoxLayout()
        label = QLabel("Einstellungen")
        label.setStyleSheet("font-size: 24pt;")  # Set font size to 24pt
        settings_layout.addWidget(label)
        
        
        # Create QListWidget for age groups
        self.age_groups_listwidget = self.create_listwidget()
        self.age_groups_senior_team_listwidget = self.create_listwidget()
        self.age_groups_senior_individual_listwidget = self.create_listwidget()
        
        tab_widget = QTabWidget()

        tab1 = QWidget()
        tab1_layout = QHBoxLayout()
        wwk_form_layout = QFormLayout()

        self.simplify_senior_groups_checkbox = QCheckBox()
        wwk_form_layout.addRow(QLabel("Senioren Altersklassen vereinfachen:"), self.simplify_senior_groups_checkbox)


        self.start_ak_wwk_combobox = QComboBox()
        wwk_form_layout.addRow(QLabel("Wellen Starterlaubniss ab:"), self.start_ak_wwk_combobox)

        self.drop_not_started_teams_checkbox = QCheckBox()
        wwk_form_layout.addRow(QLabel("Nicht angetretene Teams bei Auswertung ausschließen:"), self.drop_not_started_teams_checkbox)
        
        tab1_layout.addLayout(wwk_form_layout)
        tab1.setLayout(tab1_layout)
        tab_widget.addTab(tab1, "Wellenwettkampf")

        tab2 = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_layout.addWidget(self.age_groups_listwidget)
        ag_form_layout = QHBoxLayout()
        self.new_age_group_edit = QLineEdit()
        ag_form_layout.addWidget(QLabel("AK:"))
        ag_form_layout.addWidget(self.new_age_group_edit)
        ag_form_layout.addWidget(QPushButton("Hinzufügen", clicked=lambda: self.add_age_group(self.new_age_group_edit, self.age_groups_listwidget, self.start_ak_wwk_combobox)))
        ag_form_layout.addWidget(QPushButton("Auswahl löschen", clicked=lambda: self.delete_age_group(self.age_groups_listwidget, self.start_ak_wwk_combobox)))
        tab2_layout.addLayout(ag_form_layout)
        tab2.setLayout(tab2_layout)
        tab_widget.addTab(tab2, "Altersklassen")

        tab3 = QWidget()
        tab3_layout = QHBoxLayout()
        tab3_age_groups_layout_team = QVBoxLayout()
        tab3_layout.addLayout(tab3_age_groups_layout_team)
        tab3_age_groups_layout_team.addWidget(QLabel("Altersklassen Senioren Mannschaft"))
        tab3_age_groups_layout_team.addWidget(self.age_groups_senior_team_listwidget)
        ag_senior_team_form_layout = QHBoxLayout()
        self.new_ag_senior_team_edit = QLineEdit()
        ag_senior_team_form_layout.addWidget(QLabel("AK:"))
        ag_senior_team_form_layout.addWidget(self.new_ag_senior_team_edit)
        ag_senior_team_form_layout.addWidget(QPushButton("Hinzufügen", clicked=lambda: self.add_age_group(self.new_ag_senior_team_edit, self.age_groups_senior_team_listwidget)))
        tab3_age_groups_layout_team.addLayout(ag_senior_team_form_layout)
        tab3_age_groups_layout_team.addWidget(QPushButton("Auswahl löschen", clicked=lambda: self.delete_age_group(self.age_groups_senior_team_listwidget)))

        tab3_age_groups_layout_individual = QVBoxLayout()
        tab3_layout.addLayout(tab3_age_groups_layout_individual)
        tab3_age_groups_layout_individual.addWidget(QLabel("Altersklassen Senioren Einzel"))
        tab3_age_groups_layout_individual.addWidget(self.age_groups_senior_individual_listwidget)
        ag_senior_individual_form_layout = QHBoxLayout()
        self.new_ag_senior_individual_edit = QLineEdit()
        ag_senior_individual_form_layout.addWidget(QLabel("AK:"))
        ag_senior_individual_form_layout.addWidget(self.new_ag_senior_individual_edit)
        ag_senior_individual_form_layout.addWidget(QPushButton("Hinzufügen", clicked=lambda: self.add_age_group(self.new_ag_senior_individual_edit, self.age_groups_senior_individual_listwidget)))
        tab3_age_groups_layout_individual.addLayout(ag_senior_individual_form_layout)
        tab3_age_groups_layout_individual.addWidget(QPushButton("Auswahl löschen", clicked=lambda: self.delete_age_group(self.age_groups_senior_individual_listwidget)))
        tab3.setLayout(tab3_layout)
        tab_widget.addTab(tab3, "Altersklassen Senioren")
        
        settings_layout.addWidget(tab_widget)

        setting_buttons_layout = QHBoxLayout()
        setting_buttons_layout.addWidget(QPushButton("Speichern", clicked=self.save_settings))

        #TODO: Exportieren und Importieren von Einstellungen ermöglichen
        #setting_buttons_layout.addWidget(QPushButton("Exportieren", clicked=self.save_settings))
        #setting_buttons_layout.addWidget(QPushButton("Importieren", clicked=self.save_settings))

        setting_buttons_layout.addWidget(QPushButton("Zurücksetzten", clicked=self.restore_settings))
        settings_layout.addLayout(setting_buttons_layout)

        settings_page.setLayout(settings_layout)
        self.stacked_widget.addWidget(settings_page)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(basedir,'images','icon.ico')))
    window = MainApplication()
    window.show()
    sys.exit(app.exec())
