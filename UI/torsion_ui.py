import customtkinter as ctk
import serial
import threading
import time
import csv
from datetime import datetime
from tkinter import filedialog, messagebox

# import matplotlib.pyplot as plt

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class TorsionUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.button_color = "#d81b60"
        self.hover_color = "#ec407a"
        self.frame_color = "#fce4ec"
        self.main_bg_color = "#fff0f5"

        self.title("Torsional Testing Device")
        self.geometry("1100x820")
        self.configure(fg_color=self.main_bg_color)

        self.current_angle = 0.0
        self.current_torque = 0.0
        self.current_avg_adjusted = 0
        self.current_k = None

        self.test_running = False
        self.calibration_mode = False

        self.estop_latched = False
        self.shield_latched = False
        self.shield_present = None

        self.hard_torque_limit = 3.0

        self.ser = None
        self.reader_thread = None
        self.reading_serial = False

        self.test_data_rows = []
        self.current_test_timestamp = None
        self.save_prompt_pending = False
        self.last_completed_test_rows = []

        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color=self.main_bg_color)
        self.main_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        self.title_label = ctk.CTkLabel(
            self.main_scroll,
            text="Torsional Testing Device",
            font=("Arial", 24, "bold"),
            text_color=self.button_color
        )
        self.title_label.pack(pady=20)

        self.input_frame = ctk.CTkFrame(self.main_scroll, fg_color=self.frame_color)
        self.input_frame.pack(pady=10, padx=20, fill="x")

        self.com_label = ctk.CTkLabel(self.input_frame, text="COM Port:")
        self.com_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.com_entry = ctk.CTkEntry(self.input_frame, width=200)
        self.com_entry.grid(row=0, column=1, padx=10, pady=10)
        self.com_entry.insert(0, "COM3")

        self.com_hint = ctk.CTkLabel(
            self.input_frame,
            text="Example: COM3",
            font=("Arial", 12),
            text_color="gray"
        )
        self.com_hint.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        self.specimen_label = ctk.CTkLabel(self.input_frame, text="Specimen ID:")
        self.specimen_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.specimen_entry = ctk.CTkEntry(self.input_frame, width=200)
        self.specimen_entry.grid(row=1, column=1, padx=10, pady=10)

        self.specimen_hint = ctk.CTkLabel(
            self.input_frame,
            text="Used for saved data filename",
            font=("Arial", 12),
            text_color="gray"
        )
        self.specimen_hint.grid(row=1, column=2, padx=10, pady=10, sticky="w")

        self.speed_label = ctk.CTkLabel(self.input_frame, text="Speed (deg/s):")
        self.speed_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.speed_entry = ctk.CTkEntry(self.input_frame, width=200)
        self.speed_entry.grid(row=2, column=1, padx=10, pady=10)
        self.speed_entry.insert(0, "1.0")

        self.speed_hint = ctk.CTkLabel(
            self.input_frame,
            text="Recommended: 5 - 15 deg/s",
            font=("Arial", 12),
            text_color="gray"
        )
        self.speed_hint.grid(row=2, column=2, padx=10, pady=10, sticky="w")

        self.angle_label = ctk.CTkLabel(self.input_frame, text="Max Angle (deg):")
        self.angle_label.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        self.angle_entry = ctk.CTkEntry(self.input_frame, width=200)
        self.angle_entry.grid(row=3, column=1, padx=10, pady=10)
        self.angle_entry.insert(0, "30")

        self.angle_hint = ctk.CTkLabel(
            self.input_frame,
            text="Only set if you need specific angle, if not then set to high number (ex: 2160)",
            font=("Arial", 12),
            text_color="gray"
        )
        self.angle_hint.grid(row=3, column=2, padx=10, pady=10, sticky="w")

        self.torque_label = ctk.CTkLabel(self.input_frame, text="Max Torque (N·m):")
        self.torque_label.grid(row=4, column=0, padx=10, pady=10, sticky="w")

        self.torque_entry = ctk.CTkEntry(self.input_frame, width=200)
        self.torque_entry.grid(row=4, column=1, padx=10, pady=10)
        self.torque_entry.insert(0, "1.5")

        self.torque_hint = ctk.CTkLabel(
            self.input_frame,
            text="Range: 0 - 3.0 N·m",
            font=("Arial", 12),
            text_color="gray"
        )
        self.torque_hint.grid(row=4, column=2, padx=10, pady=10, sticky="w")

        self.button_frame = ctk.CTkFrame(self.main_scroll, fg_color=self.frame_color)
        self.button_frame.pack(pady=20, padx=20, fill="x")

        self.connect_button = ctk.CTkButton(
            self.button_frame,
            text="Connect",
            command=self.connect_device,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.connect_button.grid(row=0, column=0, padx=10, pady=10)

        self.start_button = ctk.CTkButton(
            self.button_frame,
            text="Start Test",
            command=self.start_test,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.start_button.grid(row=0, column=1, padx=10, pady=10)

        self.stop_button = ctk.CTkButton(
            self.button_frame,
            text="Stop Test",
            command=self.stop_test,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.stop_button.grid(row=0, column=2, padx=10, pady=10)

        self.calibration_button = ctk.CTkButton(
            self.button_frame,
            text="Calibration Mode",
            command=self.toggle_calibration_mode,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.calibration_button.grid(row=0, column=3, padx=10, pady=10)

        self.clear_fault_button = ctk.CTkButton(
            self.button_frame,
            text="Clear Fault Latches",
            command=self.clear_fault_latches,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.clear_fault_button.grid(row=0, column=4, padx=10, pady=10)

        self.status_frame = ctk.CTkFrame(self.main_scroll, fg_color=self.frame_color)
        self.status_frame.pack(pady=20, padx=20, fill="x")

        self.connection_status = ctk.CTkLabel(
            self.status_frame,
            text="Connection: Not Connected",
            font=("Arial", 16)
        )
        self.connection_status.pack(pady=5)

        self.test_status = ctk.CTkLabel(
            self.status_frame,
            text="Test Status: Idle",
            font=("Arial", 16)
        )
        self.test_status.pack(pady=5)

        self.shield_status_label = ctk.CTkLabel(
            self.status_frame,
            text="Shield Status: Unknown",
            font=("Arial", 16)
        )
        self.shield_status_label.pack(pady=5)

        self.angle_display = ctk.CTkLabel(
            self.status_frame,
            text="Current Angle: 0.00 deg",
            font=("Arial", 16)
        )
        self.angle_display.pack(pady=5)

        self.torque_display = ctk.CTkLabel(
            self.status_frame,
            text="Current Torque: 0.00 N·m",
            font=("Arial", 16)
        )
        self.torque_display.pack(pady=5)

        self.calibration_frame = ctk.CTkFrame(self.main_scroll, fg_color=self.frame_color)

        self.calibration_title = ctk.CTkLabel(
            self.calibration_frame,
            text="Calibration Mode",
            font=("Arial", 18, "bold"),
            text_color=self.button_color
        )
        self.calibration_title.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 5), sticky="w")

        instructions_text = (
            "Calibration Instructions:\n"
            "1. Make sure the clamp is installed on the torsion sensor.\n"
            "2. Attach the calibration lever securely to the clamp.\n"
            "3. Make sure the lever is unsupported and not being touched.\n"
            "4. Press 'Tare Sensor' with the lever attached and no weight applied.\n"
            "5. Enter the lever length in meters.\n"
            "6. Hang the known calibration weight from the lever.\n"
            "7. Enter the mass in kilograms.\n"
            "8. Wait for the reading to settle.\n"
            "9. Press 'Calculate Suggested K'.\n"
            "10. Review the suggested K and press 'Send New K'.\n"
            "11. Remove the weight and verify the reading if needed."
        )

        self.instructions_label = ctk.CTkLabel(
            self.calibration_frame,
            text=instructions_text,
            justify="left",
            anchor="w",
            font=("Arial", 13)
        )
        self.instructions_label.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="w")

        self.lever_label = ctk.CTkLabel(self.calibration_frame, text="Lever Length (m):")
        self.lever_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.lever_entry = ctk.CTkEntry(self.calibration_frame, width=200)
        self.lever_entry.grid(row=2, column=1, padx=10, pady=10)
        self.lever_entry.insert(0, "0.10")

        self.mass_label = ctk.CTkLabel(self.calibration_frame, text="Mass (kg):")
        self.mass_label.grid(row=3, column=0, padx=10, pady=10, sticky="w")

        self.mass_entry = ctk.CTkEntry(self.calibration_frame, width=200)
        self.mass_entry.grid(row=3, column=1, padx=10, pady=10)
        self.mass_entry.insert(0, "0.50")

        self.expected_torque_label = ctk.CTkLabel(
            self.calibration_frame,
            text="Expected Torque: 0.0000 N·m",
            font=("Arial", 14)
        )
        self.expected_torque_label.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="w")

        self.avg_adjusted_label = ctk.CTkLabel(
            self.calibration_frame,
            text="Avg Adjusted Reading: 0",
            font=("Arial", 14)
        )
        self.avg_adjusted_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="w")

        self.k_label = ctk.CTkLabel(
            self.calibration_frame,
            text="Current K: Not Received",
            font=("Arial", 14)
        )
        self.k_label.grid(row=6, column=0, columnspan=3, padx=10, pady=10, sticky="w")

        self.tare_button = ctk.CTkButton(
            self.calibration_frame,
            text="Tare Sensor",
            command=self.tare_sensor,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.tare_button.grid(row=7, column=0, padx=10, pady=10)

        self.calculate_button = ctk.CTkButton(
            self.calibration_frame,
            text="Calculate Suggested K",
            command=self.calculate_suggested_k,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.calculate_button.grid(row=7, column=1, padx=10, pady=10)

        self.get_k_button = ctk.CTkButton(
            self.calibration_frame,
            text="Get Current K",
            command=self.get_current_k,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.get_k_button.grid(row=7, column=2, padx=10, pady=10)

        self.set_k_label = ctk.CTkLabel(self.calibration_frame, text="New K:")
        self.set_k_label.grid(row=8, column=0, padx=10, pady=10, sticky="w")

        self.set_k_entry = ctk.CTkEntry(self.calibration_frame, width=200)
        self.set_k_entry.grid(row=8, column=1, padx=10, pady=10)

        self.send_k_button = ctk.CTkButton(
            self.calibration_frame,
            text="Send New K",
            command=self.send_new_k,
            fg_color=self.button_color,
            hover_color=self.hover_color
        )
        self.send_k_button.grid(row=8, column=2, padx=10, pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def send_command(self, command_text):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((command_text + "\n").encode("utf-8"))
            except Exception as e:
                self.test_status.configure(text=f"Test Status: Send error: {str(e)}")
        else:
            self.test_status.configure(text="Test Status: Not connected to Arduino")

    def connect_device(self):
        port_name = self.com_entry.get().strip()

        if self.ser and self.ser.is_open:
            self.connection_status.configure(text=f"Connection: Already connected to {port_name}")
            return

        try:
            self.ser = serial.Serial(port_name, 9600, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            self.connection_status.configure(text=f"Connection: Connected to {port_name}")
            self.test_status.configure(text="Test Status: Arduino connected")
            self.shield_status_label.configure(text="Shield Status: Checking...")

            self.reading_serial = True
            self.reader_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.reader_thread.start()

            self.after(500, lambda: self.send_command("GET_SHIELD_STATUS"))

        except Exception as e:
            self.connection_status.configure(text="Connection: Failed")
            self.test_status.configure(text=f"Test Status: {str(e)}")

    def disconnect_serial(self):
        self.reading_serial = False

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

        self.ser = None
        self.connection_status.configure(text="Connection: Not Connected")
        self.shield_status_label.configure(text="Shield Status: Unknown")

    def toggle_calibration_mode(self):
        self.calibration_mode = not self.calibration_mode

        if self.calibration_mode:
            self.calibration_frame.pack(pady=10, padx=20, fill="x")
            self.test_status.configure(text="Test Status: Calibration mode enabled")
            self.after(100, lambda: self.main_scroll._parent_canvas.yview_moveto(1.0))
        else:
            self.calibration_frame.pack_forget()
            self.test_status.configure(text="Test Status: Calibration mode disabled")

    def tare_sensor(self):
        self.send_command("ZERO_TORQUE")
        self.test_status.configure(text="Test Status: Tare command sent")

    def calculate_suggested_k(self):
        try:
            lever_length = float(self.lever_entry.get().strip())
            mass = float(self.mass_entry.get().strip())

            if lever_length <= 0 or mass <= 0:
                self.test_status.configure(text="Test Status: Lever length and mass must be greater than 0")
                return

            expected_torque = lever_length * mass * 9.81
            self.expected_torque_label.configure(text=f"Expected Torque: {expected_torque:.4f} N·m")

            if self.current_avg_adjusted == 0:
                self.test_status.configure(text="Test Status: Avg adjusted reading is 0, cannot calculate K")
                return

            suggested_k = abs(expected_torque / self.current_avg_adjusted)

            self.set_k_entry.delete(0, "end")
            self.set_k_entry.insert(0, f"{suggested_k:.8f}")
            self.test_status.configure(text="Test Status: Suggested positive K calculated")

        except ValueError:
            self.test_status.configure(text="Test Status: Invalid calibration input")

    def get_current_k(self):
        self.send_command("GET_K")

    def send_new_k(self):
        try:
            new_k = float(self.set_k_entry.get().strip())
            new_k = abs(new_k)

            self.set_k_entry.delete(0, "end")
            self.set_k_entry.insert(0, f"{new_k:.8f}")

            self.send_command(f"SET_K:{new_k:.8f}")
            self.test_status.configure(text=f"Test Status: Sent new K = {new_k:.8f}")

        except ValueError:
            self.test_status.configure(text="Test Status: Invalid K entered")

    def clear_fault_latches(self):
        if self.estop_latched:
            self.send_command("CLEAR_ESTOP")

        if self.shield_latched:
            self.send_command("CLEAR_SHIELD")

        self.test_status.configure(text="Test Status: Clear fault command sent")

    def reset_test_data(self):
        self.test_data_rows = []
        self.current_test_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.save_prompt_pending = False

    def write_log_row(self):
        now_string = datetime.now().strftime("%H:%M:%S")
        self.test_data_rows.append([
            now_string,
            f"{self.current_angle:.2f}",
            f"{self.current_torque:.4f}"
        ])

    # PLOT FUNCTION COMMENTED OUT FOR STABILITY
    # def show_post_test_plot(self):
    #     pass

    def prompt_save_data(self, title="Save Test Data", prompt="Do you want to save this test data?"):
        if self.save_prompt_pending:
            return

        self.save_prompt_pending = True

        if len(self.test_data_rows) == 0:
            self.test_status.configure(text="Test Status: No test data to save")
            self.save_prompt_pending = False
            return

        self.last_completed_test_rows = self.test_data_rows.copy()

        save_choice = messagebox.askyesno(title, prompt)

        if not save_choice:
            self.test_status.configure(text="Test Status: Test ended, data discarded")
            self.test_data_rows = []
            self.save_prompt_pending = False
            return

        specimen_id = self.specimen_entry.get().strip()
        if specimen_id == "":
            specimen_id = "No_ID"

        default_filename = f"{specimen_id}_{self.current_test_timestamp}.csv"

        file_path = filedialog.asksaveasfilename(
            title="Save Test Data",
            defaultextension=".csv",
            initialfile=default_filename,
            filetypes=[("CSV files", "*.csv")]
        )

        if not file_path:
            self.test_status.configure(text="Test Status: Save cancelled, data kept in memory")
            self.save_prompt_pending = False
            return

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Time", "Angle_deg", "Torque_Nm"])
                writer.writerows(self.test_data_rows)

            self.test_status.configure(text=f"Test Status: Data saved to {file_path}")
            self.test_data_rows = []

        except Exception as e:
            self.test_status.configure(text=f"Test Status: Could not save file: {str(e)}")

        self.save_prompt_pending = False

    def start_test(self):
        if self.estop_latched:
            messagebox.showwarning(
                "E-Stop Latched",
                "The system is latched from an E-stop event. Reset the E-stop and clear the latch before starting a new test."
            )
            return

        if self.shield_latched:
            messagebox.showwarning(
                "Shield Latch Active",
                "The system is latched from a shield event. Make sure the shield is in place and clear the shield latch before starting a new test."
            )
            return

        if self.shield_present is None:
            messagebox.showwarning(
                "Shield Status Unknown",
                "Shield status has not been received from the controller yet. Make sure the shield is in place and try again."
            )
            self.send_command("GET_SHIELD_STATUS")
            return

        if not self.shield_present:
            messagebox.showwarning(
                "Shield Not In Place",
                "Safety shield is not in place. Please close the shield before starting the test."
            )
            return

        try:
            specimen_id = self.specimen_entry.get().strip()
            speed = float(self.speed_entry.get())
            max_angle = float(self.angle_entry.get())
            user_torque_limit = float(self.torque_entry.get())

            if speed <= 0:
                self.test_status.configure(text="Test Status: Speed must be greater than 0")
                return

            if max_angle <= 0:
                self.test_status.configure(text="Test Status: Max angle must be greater than 0")
                return

            if user_torque_limit <= 0:
                self.test_status.configure(text="Test Status: Max torque must be greater than 0")
                return

            effective_torque_limit = min(user_torque_limit, self.hard_torque_limit)

            if user_torque_limit != effective_torque_limit:
                self.torque_entry.delete(0, "end")
                self.torque_entry.insert(0, str(effective_torque_limit))

            self.current_angle = 0.0
            self.current_torque = 0.0
            self.current_avg_adjusted = 0

            self.test_running = True
            self.reset_test_data()

            self.angle_display.configure(text="Current Angle: 0.00 deg")
            self.torque_display.configure(text="Current Torque: 0.00 N·m")

            self.write_log_row()

            start_command = f"START,{speed},{max_angle},{effective_torque_limit}"
            self.send_command(start_command)

            self.test_status.configure(
                text=(
                    f"Test Status: Running | ID={specimen_id if specimen_id else 'No ID'} | "
                    f"Speed={speed:.2f} deg/s | "
                    f"Max Angle={max_angle:.2f} deg | "
                    f"Max Torque={effective_torque_limit:.2f} N·m"
                )
            )

        except ValueError:
            self.test_status.configure(text="Test Status: Invalid input entered")

    def stop_test(self):
        was_running = self.test_running
        self.test_running = False
        self.send_command("STOP")
        self.test_status.configure(text="Test Status: Stopped")

        if was_running:
            self.after(200, self.prompt_save_data)

    def handle_estop_triggered(self):
        was_running = self.test_running
        self.test_running = False
        self.estop_latched = True
        self.start_button.configure(state="disabled")
        self.test_status.configure(text="Test Status: E-stop pressed, test ended")
        self.send_command("STOP")

        if was_running:
            self.after(
                200,
                lambda: self.prompt_save_data(
                    title="Emergency Stop",
                    prompt=(
                        "E-stop pressed. Test stopped.\n\n"
                        "Reset the E-stop and clear the E-stop latch before starting a new test.\n\n"
                        "Would you like to save your data?"
                    )
                )
            )
        else:
            messagebox.showwarning(
                "Emergency Stop",
                "E-stop pressed. Reset the E-stop and clear the E-stop latch before starting a new test."
            )

    def handle_shield_open(self):
        was_running = self.test_running
        self.test_running = False
        self.shield_latched = True
        self.shield_present = False
        self.start_button.configure(state="disabled")
        self.shield_status_label.configure(text="Shield Status: Open / Not In Place")
        self.test_status.configure(text="Test Status: Safety shield opened, test ended")
        self.send_command("STOP")

        if was_running:
            self.after(
                200,
                lambda: self.prompt_save_data(
                    title="Safety Shield Opened",
                    prompt=(
                        "Safety shield opened. Test stopped.\n\n"
                        "Close the shield and clear the shield latch before starting a new test.\n\n"
                        "Would you like to save your data?"
                    )
                )
            )

    def read_serial_data(self):
        while self.reading_serial and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    self.after(0, self.parse_serial_line, line)
            except Exception as e:
                self.after(0, lambda err=str(e): self.test_status.configure(
                    text=f"Test Status: Serial read error: {err}"
                ))
                break

    def parse_serial_line(self, line):
        try:
            if line == "ESTOP_TRIGGERED" or line == "STATUS:ESTOP_TRIGGERED":
                self.handle_estop_triggered()
                return

            if line == "STATUS:SHIELD_OPEN":
                self.shield_present = False
                self.shield_status_label.configure(text="Shield Status: Open / Not In Place")

                if self.test_running:
                    self.handle_shield_open()

                return

            if line == "STATUS:SHIELD_CLOSED":
                self.shield_present = True
                self.shield_status_label.configure(text="Shield Status: Closed / In Place")
                if not self.shield_latched:
                    self.test_status.configure(text="Test Status: Shield confirmed in place")
                return

            if line == "ESTOP_CLEARED" or line == "STATUS:ESTOP_CLEARED":
                self.estop_latched = False
                if not self.shield_latched:
                    self.start_button.configure(state="normal")
                self.test_status.configure(text="Test Status: E-stop cleared")
                return

            if line == "STATUS:SHIELD_CLEARED":
                self.shield_latched = False
                self.shield_present = True
                if not self.estop_latched:
                    self.start_button.configure(state="normal")
                self.test_status.configure(text="Test Status: Shield latch cleared")
                return

            if line.startswith("STATUS:K_VALUE:"):
                value = float(line.replace("STATUS:K_VALUE:", "").strip())
                self.current_k = value
                self.k_label.configure(text=f"Current K: {self.current_k:.8f}")
                self.test_status.configure(text=f"Test Status: Current K received = {self.current_k:.8f}")
                return

            if line.startswith("STATUS:K_UPDATED:"):
                value = float(line.replace("STATUS:K_UPDATED:", "").strip())
                self.current_k = value
                self.k_label.configure(text=f"Current K: {self.current_k:.8f}")
                self.test_status.configure(text=f"Test Status: K updated = {self.current_k:.8f}")
                return

            if line.startswith("STATUS:"):
                status_message = line.replace("STATUS:", "").strip()

                display_message = status_message
                if status_message == "MAX_TORQUE_REACHED":
                    display_message = "Maximum torque reached"
                elif status_message == "MAX_ANGLE_REACHED":
                    display_message = "Maximum angle reached"
                elif status_message == "STOPPED":
                    display_message = "Stopped"
                elif status_message == "BOARD1_READY":
                    display_message = "Board 1 ready"

                self.test_status.configure(text=f"Test Status: {display_message}")

                if status_message in ["MAX_TORQUE_REACHED", "MAX_ANGLE_REACHED", "STOPPED"]:
                    was_running = self.test_running
                    self.test_running = False

                    if was_running:
                        self.after(200, self.prompt_save_data)

                return

            if line.startswith("ERROR:"):
                self.test_status.configure(text=f"Test Status: {line}")
                return

            parts = line.split(",")

            for part in parts:
                if ":" not in part:
                    continue

                key, value = part.split(":", 1)
                key = key.strip()
                value = value.strip()

                if key == "TORQUE_NM":
                    self.current_torque = float(value)

                elif key == "ANGLE":
                    self.current_angle = float(value)

                elif key == "AVG_ADJUSTED":
                    self.current_avg_adjusted = int(float(value))

                elif key == "K":
                    self.current_k = float(value)
                    self.k_label.configure(text=f"Current K: {self.current_k:.8f}")

            self.angle_display.configure(text=f"Current Angle: {self.current_angle:.2f} deg")
            self.torque_display.configure(text=f"Current Torque: {self.current_torque:.4f} N·m")

            if self.calibration_mode:
                self.avg_adjusted_label.configure(
                    text=f"Avg Adjusted Reading: {self.current_avg_adjusted}"
                )

            if self.test_running:
                self.write_log_row()

        except Exception:
            self.test_status.configure(text=f"Test Status: Bad data -> {line}")

    def on_close(self):
        self.reading_serial = False
        self.disconnect_serial()
        self.destroy()


if __name__ == "__main__":
    app = TorsionUI()
    app.mainloop()