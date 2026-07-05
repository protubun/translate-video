import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QComboBox, QFileDialog, 
    QCheckBox, QProgressBar, QTextEdit, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon

# Pipeline steps import
from extract_audio import verify_ffmpeg_installation, validate_video_file, extract_audio
from transcribe import transcribe_audio
from translate import translate_segments
from format_subtitles import format_subtitles
from write_srt import write_srt_file, write_ass_file, embed_subtitles
from dubbing import generate_voiceover_audio, combine_video_and_voiceover
from dual_subtitles import generate_dual_subtitles

class WorkerSignals(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class PipelineWorker(threading.Thread):
    def __init__(self, video_path, target_lang, source_lang, model_size, embed_mode, denoise, dual_subs, dub, mute_audio, output_dir):
        super().__init__()
        self.video_path = video_path
        self.target_lang = target_lang
        self.source_lang = source_lang if source_lang != "Auto-Detect" else None
        self.model_size = model_size
        self.embed_mode = embed_mode if embed_mode != "None" else None
        self.denoise = denoise
        self.dual_subs = dual_subs
        self.dub = dub
        self.mute_audio = mute_audio
        self.output_dir = output_dir
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.progress.emit(5)
            self.signals.log.emit("<b>[Stage 0]</b> Running pre-execution environment diagnostics...")
            verify_ffmpeg_installation()
            
            self.signals.progress.emit(10)
            self.signals.log.emit("<b>[Stage 0]</b> Analyzing video container metadata & streams...")
            validate_video_file(self.video_path)

            video_base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            temp_audio_path = os.path.join(self.output_dir, f"{video_base_name}_temp_audio.wav")
            output_srt_path = os.path.join(self.output_dir, f"{video_base_name}.srt")
            output_ass_path = os.path.join(self.output_dir, f"{video_base_name}.ass")
            output_video_path = os.path.join(self.output_dir, f"{video_base_name}_subtitled.mp4")
            output_dub_audio_path = os.path.join(self.output_dir, f"{video_base_name}_dubbed.wav")
            output_dub_video_path = os.path.join(self.output_dir, f"{video_base_name}_dubbed.mp4")

            # Stage 1: Audio Extraction
            self.signals.progress.emit(15)
            self.signals.log.emit("<b>[Stage 1]</b> Extracting audio track from video container...")
            if self.denoise:
                self.signals.log.emit("<b>[Stage 1]</b> Background Noise Reduction enabled. Applying speech bandpass filter...")
            extract_audio(self.video_path, temp_audio_path, apply_denoise=self.denoise)
            self.signals.log.emit(f"<b>[Stage 1]</b> Audio extracted successfully to raw file.")

            # Stage 2: Transcription
            self.signals.progress.emit(30)
            self.signals.log.emit(f"<b>[Stage 2]</b> Initializing Whisper model '{self.model_size}' and starting speech-to-text transcription...")
            raw_segments = transcribe_audio(
                audio_path=temp_audio_path,
                model_size=self.model_size,
                source_lang=self.source_lang
            )
            self.signals.log.emit(f"<b>[Stage 2]</b> Transcription completed. Found {len(raw_segments)} dialogue segments.")

            # Stage 3: Translation
            self.signals.progress.emit(50)
            self.signals.log.emit(f"<b>[Stage 3]</b> Launching parallel translators to target language '{self.target_lang}'...")
            translated_segments = translate_segments(
                segments=raw_segments,
                target_lang=self.target_lang,
                source_lang=self.source_lang or "auto"
            )
            self.signals.log.emit("<b>[Stage 3]</b> Dialogues translated successfully.")

            # Stage 4: Re-chunking & Layout Formatting
            self.signals.progress.emit(65)
            self.signals.log.emit("<b>[Stage 4]</b> Re-chunking subtitle cards using linguistic sentence boundaries & pacing times...")
            formatted_translated_segments = format_subtitles(segments=translated_segments)

            if self.dual_subs:
                self.signals.log.emit("<b>[Stage 4]</b> Dual-Subtitles active. Merging original and translated text layers...")
                formatted_raw_segments = format_subtitles(segments=raw_segments)
                final_segments = generate_dual_subtitles(
                    original_segments=formatted_raw_segments,
                    translated_segments=formatted_translated_segments
                )
            else:
                final_segments = formatted_translated_segments

            # Stage 5: Output Files Generation
            self.signals.progress.emit(80)
            self.signals.log.emit("<b>[Stage 5]</b> Generating output files (.srt & stylized .ass)...")
            write_srt_file(final_segments, output_srt_path)
            write_ass_file(final_segments, output_ass_path)

            if self.embed_mode:
                self.signals.log.emit(f"<b>[Stage 5]</b> Embedding subtitles into video copy (Mode: {self.embed_mode})...")
                embed_subtitles(
                    video_path=self.video_path,
                    srt_path=output_srt_path,
                    output_video_path=output_video_path,
                    embed_mode=self.embed_mode
                )

            # Optional Dubbing
            if self.dub:
                self.signals.progress.emit(90)
                self.signals.log.emit("<b>[Optional Stage]</b> Synthesizing translation voiceover & stretching timelines...")
                generate_voiceover_audio(
                    segments=formatted_translated_segments,
                    target_lang=self.target_lang,
                    output_audio_path=output_dub_audio_path
                )
                self.signals.log.emit("<b>[Optional Stage]</b> Mixing synthesized voice tracks into video...")
                combine_video_and_voiceover(
                    video_path=self.video_path,
                    voiceover_path=output_dub_audio_path,
                    output_video_path=output_dub_video_path,
                    mute_original_audio=self.mute_audio
                )

            # Cleanup
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)

            self.signals.progress.emit(100)
            success_msg = f"<font color='#00E676'><b>✔ Pipeline completed successfully!</b></font><br/>Subtitles: {output_srt_path}"
            if self.embed_mode:
                success_msg += f"<br/>Subtitled Video: {output_video_path}"
            if self.dub:
                success_msg += f"<br/>Dubbed Video: {output_dub_video_path}"
            self.signals.finished.emit(success_msg)

        except Exception as e:
            self.signals.error.emit(str(e))

class ModernSubTranslatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Subtitle Translator & Dubber")
        self.resize(900, 680)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
            }
            QWidget {
                color: #c9d1d9;
                font-family: 'Segoe UI', -apple-system, Roboto, sans-serif;
            }
            QLabel {
                font-weight: 500;
            }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                color: #c9d1d9;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            QLineEdit, QComboBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                color: #c9d1d9;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #58a6ff;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #30363d;
                border-radius: 4px;
                background-color: #0d1117;
            }
            QCheckBox::indicator:checked {
                background-color: #238636;
                border-color: #2ea043;
            }
            QProgressBar {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #1f6feb, stop:1 #58a6ff);
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #8b949e;
                font-family: 'Courier New', Courier, monospace;
            }
        """)

        # Central container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Header card style
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #161b22, stop:1 #0d1117);
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(20, 20, 20, 20)
        
        title_sub_layout = QVBoxLayout()
        title_label = QLabel("AI Video Subtitle Translator & Dubber")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #58a6ff; border: none;")
        subtitle_label = QLabel("High-fidelity modular transcription, translation, and localized vocal speech cloning pipeline")
        subtitle_label.setFont(QFont("Segoe UI", 10))
        subtitle_label.setStyleSheet("color: #8b949e; border: none;")
        title_sub_layout.addWidget(title_label)
        title_sub_layout.addWidget(subtitle_label)
        header_layout.addLayout(title_sub_layout)

        # Add drop shadow to header card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        header_card.setGraphicsEffect(shadow)

        main_layout.addWidget(header_card)

        # Main Body - Two Column Layout
        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        # Left Column - Form & Controls
        left_column = QFrame()
        left_column.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(16)

        # Input video file row
        file_label = QLabel("Source Video File")
        file_label.setStyleSheet("border: none; font-size: 13px; color: #8b949e;")
        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderOfText = "Choose target mp4, mkv, avi..." # compat
        self.file_input.setPlaceholderText("Select video file...")
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_video)
        file_row.addWidget(self.file_input)
        file_row.addWidget(self.browse_btn)

        # Language selection row
        lang_row = QHBoxLayout()
        source_lang_layout = QVBoxLayout()
        source_lang_label = QLabel("Source Language")
        source_lang_label.setStyleSheet("border: none; font-size: 13px; color: #8b949e;")
        self.source_lang_box = QComboBox()
        self.source_lang_box.addItems(["Auto-Detect", "en", "es", "fr", "de", "it", "ja", "ko", "zh-CN", "bg"])
        source_lang_layout.addWidget(source_lang_label)
        source_lang_layout.addWidget(self.source_lang_box)

        target_lang_layout = QVBoxLayout()
        target_lang_label = QLabel("Target Language")
        target_lang_label.setStyleSheet("border: none; font-size: 13px; color: #8b949e;")
        self.target_lang_box = QComboBox()
        self.target_lang_box.addItems(["es", "fr", "de", "it", "en", "ja", "ko", "zh-CN", "bg", "ar"])
        target_lang_layout.addWidget(target_lang_label)
        target_lang_layout.addWidget(self.target_lang_box)

        lang_row.addLayout(source_lang_layout)
        lang_row.addLayout(target_lang_layout)

        # Config Row: Whisper & Video Embed modes
        config_row = QHBoxLayout()
        model_layout = QVBoxLayout()
        model_label = QLabel("Whisper Model Size")
        model_label.setStyleSheet("border: none; font-size: 13px; color: #8b949e;")
        self.model_box = QComboBox()
        self.model_box.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.model_box.setCurrentText("small")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_box)

        embed_layout = QVBoxLayout()
        embed_label = QLabel("Burn-in Subtitles")
        embed_label.setStyleSheet("border: none; font-size: 13px; color: #8b949e;")
        self.embed_box = QComboBox()
        self.embed_box.addItems(["None", "soft", "burn"])
        embed_layout.addWidget(embed_label)
        embed_layout.addWidget(self.embed_box)

        config_row.addLayout(model_layout)
        config_row.addLayout(embed_layout)

        # Advanced pipeline configurations check boxes
        adv_layout = QVBoxLayout()
        adv_label = QLabel("Advanced Pipeline Features")
        adv_label.setStyleSheet("border: none; font-size: 13px; font-weight: bold; color: #58a6ff; margin-top: 8px;")
        adv_layout.addWidget(adv_label)

        self.denoise_cb = QCheckBox("Background Speech Denoising (FFmpeg)")
        self.dual_sub_cb = QCheckBox("Dual-Language Stacked Subtitles")
        self.dub_cb = QCheckBox("AI Vocal Voiceover Dubbing (gTTS)")
        self.mute_audio_cb = QCheckBox("Mute Native Video Track Completely (Dub Mode)")
        self.mute_audio_cb.setStyleSheet("margin-left: 20px; color: #8b949e;")

        adv_layout.addWidget(self.denoise_cb)
        adv_layout.addWidget(self.dual_sub_cb)
        adv_layout.addWidget(self.dub_cb)
        adv_layout.addWidget(self.mute_audio_cb)

        # Build Left controls layout
        left_layout.addWidget(file_label)
        left_layout.addLayout(file_row)
        left_layout.addLayout(lang_row)
        left_layout.addLayout(config_row)
        left_layout.addLayout(adv_layout)
        left_layout.addStretch()

        # Action Execution button
        self.run_btn = QPushButton("⚡ Execute Subtitle & Dub Pipeline")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                border: 1px solid #2ea043;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #8b949e;
            }
        """)
        self.run_btn.clicked.connect(self.start_pipeline)
        left_layout.addWidget(self.run_btn)

        body_layout.addWidget(left_column, stretch=1)

        # Right Column - Dynamic Live Logs
        right_column = QFrame()
        right_column.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(12)

        log_label = QLabel("Live Diagnostics Console")
        log_label.setStyleSheet("border: none; font-size: 13px; color: #58a6ff; font-weight: bold;")
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setHtml("<font color='#8b949e'>Pipeline Idle. Select input file and hit execute...</font>")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(24)

        right_layout.addWidget(log_label)
        right_layout.addWidget(self.log_console)
        right_layout.addWidget(self.progress_bar)

        body_layout.addWidget(right_column, stretch=1)
        main_layout.addLayout(body_layout)

    def browse_video(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Source Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov)"
        )
        if filename:
            self.file_input.setText(filename)

    def start_pipeline(self):
        video = self.file_input.text().strip()
        if not video:
            self.log_console.setHtml("<font color='#ff7b72'><b>[Error]</b> Please select a valid video file to translate.</font>")
            return

        self.run_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_console.clear()

        # Instantiate pipeline execution thread
        worker = PipelineWorker(
            video_path=video,
            target_lang=self.target_lang_box.currentText(),
            source_lang=self.source_lang_box.currentText(),
            model_size=self.model_box.currentText(),
            embed_mode=self.embed_box.currentText(),
            denoise=self.denoise_cb.isChecked(),
            dual_subs=self.dual_sub_cb.isChecked(),
            dub=self.dub_cb.isChecked(),
            mute_audio=self.mute_audio_cb.isChecked(),
            output_dir="./output"
        )

        worker.signals.log.connect(self.append_log)
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.pipeline_finished)
        worker.signals.error.connect(self.pipeline_failed)
        worker.start()

    def append_log(self, text):
        self.log_console.append(text)

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def pipeline_finished(self, msg):
        self.log_console.append(f"<br/>{msg}")
        self.run_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

    def pipeline_failed(self, err_msg):
        self.log_console.append(f"<br/><font color='#ff7b72'><b>[-] Pipeline Failed:</b> {err_msg}</font>")
        self.run_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

def main():
    app = QApplication(sys.argv)
    gui = ModernSubTranslatorGUI()
    gui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
