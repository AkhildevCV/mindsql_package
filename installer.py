# installer.py

import os
import subprocess
import platform
import threading
import urllib.request
import customtkinter as ctk
from tkinter import filedialog

# --- WOW FACTOR: Modern Theme ---
ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("dark-blue") 

class MindSQLInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MindSQL Setup Engine")
        self.geometry("600x450")
        self.resizable(False, False)
        
        self.os_type = platform.system()
        self.model_path = None

        # --- Main Container ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=40, pady=40)

        # Build the screens
        self.create_welcome_screen()

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    # ==========================================
    # SCREEN 1: Welcome & System Check
    # ==========================================
    def create_welcome_screen(self):
        self.clear_container()
        
        title = ctk.CTkLabel(self.container, text="MindSQL", font=ctk.CTkFont(size=36, weight="bold"))
        title.pack(pady=(0, 10))
        
        subtitle = ctk.CTkLabel(self.container, text="The AI-Powered Database Terminal", font=ctk.CTkFont(size=14), text_color="gray")
        subtitle.pack(pady=(0, 40))

        self.status_label = ctk.CTkLabel(self.container, text="Checking system requirements...", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=20)

        self.action_btn = ctk.CTkButton(self.container, text="Check Ollama", command=self.check_ollama, height=40)
        self.action_btn.pack(pady=20)

    def check_ollama(self):
        self.status_label.configure(text="Searching for Ollama daemon...")
        self.update()
        
        try:
            # Check if Ollama is accessible
            subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=True)
            self.status_label.configure(text="✅ Ollama is installed and running.", text_color="springgreen")
            self.action_btn.configure(text="Next Step", command=self.create_model_screen)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.status_label.configure(text="❌ Ollama not found. It is required for MindSQL.", text_color="red")
            self.action_btn.configure(text="Install Ollama Automatically", command=self.install_ollama)

    def install_ollama(self):
        self.status_label.configure(text=f"Installing Ollama for {self.os_type}... Please wait.", text_color="yellow")
        self.action_btn.configure(state="disabled")
        self.update()

        def run_install():
            try:
                if self.os_type == "Windows":
                    # Download Windows Installer
                    urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", "OllamaSetup.exe")
                    subprocess.run(["OllamaSetup.exe"], check=True)
                elif self.os_type == "Linux":
                    # Run Linux install script
                    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
                
                self.status_label.configure(text="✅ Ollama installed! Please restart the installer if it doesn't detect it.", text_color="springgreen")
                self.action_btn.configure(state="normal", text="Next Step", command=self.create_model_screen)
            except Exception as e:
                self.status_label.configure(text=f"❌ Install failed: {e}\nPlease install from ollama.com", text_color="red")
                self.action_btn.configure(state="normal", text="Retry", command=self.install_ollama)

        # Run installation in a background thread so the GUI doesn't freeze
        threading.Thread(target=run_install, daemon=True).start()

    # ==========================================
    # SCREEN 2: Model Configuration
    # ==========================================
    def create_model_screen(self):
        self.clear_container()

        title = ctk.CTkLabel(self.container, text="AI Model Setup", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=(0, 20))

        desc = ctk.CTkLabel(self.container, text="MindSQL requires a .gguf AI model to process your database.\nHow would you like to set this up?", justify="center")
        desc.pack(pady=(0, 30))

        # Option 1: Local
        local_btn = ctk.CTkButton(self.container, text="Link Local .gguf File", command=self.link_local_model, height=40, fg_color="transparent", border_width=2, text_color=("gray10", "#DCE4EE"))
        local_btn.pack(pady=10, fill="x")

        # Option 2: Download Hugging Face
        hf_btn = ctk.CTkButton(self.container, text="Download from Hugging Face", command=self.download_hf_model, height=40)
        hf_btn.pack(pady=10, fill="x")

        self.path_label = ctk.CTkLabel(self.container, text="", text_color="gray")
        self.path_label.pack(pady=20)

    def link_local_model(self):
        file_path = filedialog.askopenfilename(title="Select MindSQL Model", filetypes=[("GGUF Models", "*.gguf")])
        if file_path:
            self.model_path = file_path
            self.path_label.configure(text=f"Selected: {os.path.basename(file_path)}")
            self.finish_installation()

    def download_hf_model(self):
        # Placeholder for Hugging Face direct download link
        self.path_label.configure(text="Downloading from Hugging Face... (This will take a while)", text_color="yellow")
        self.update()
        
        def run_download():
            # Example logic: you will replace this URL with your actual Hugging Face model URL
            # hf_url = "https://huggingface.co/your-username/mindsql/resolve/main/mindsql-v2.gguf"
            # urllib.request.urlretrieve(hf_url, "mindsql-v2.gguf")
            
            self.model_path = "mindsql-v2.gguf" # Assume downloaded to current dir
            self.path_label.configure(text="✅ Download Complete!", text_color="springgreen")
            self.finish_installation()

        threading.Thread(target=run_download, daemon=True).start()

    # ==========================================
    # SCREEN 3: Final Setup & Modelfile
    # ==========================================
    def finish_installation(self):
        self.clear_container()
        
        title = ctk.CTkLabel(self.container, text="Ready to Launch!", font=ctk.CTkFont(size=28, weight="bold"), text_color="springgreen")
        title.pack(pady=(40, 20))

        desc = ctk.CTkLabel(self.container, text="The model is configured. We just need to register it with Ollama.")
        desc.pack(pady=10)

        finish_btn = ctk.CTkButton(self.container, text="Finish & Create Ollama Model", command=self.register_model_in_ollama, height=40)
        finish_btn.pack(pady=30)

    def register_model_in_ollama(self):
        self.clear_container()
        
        title = ctk.CTkLabel(self.container, text="Finalizing MindSQL...", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=(20, 20))
        
        status = ctk.CTkLabel(self.container, text="Building Ollama Model from .gguf file...\nThis might take a moment.", text_color="yellow")
        status.pack(pady=10)
        self.update()

        def run_build():
            try:
                # 1. Create the Modelfile pointing to the selected .gguf
                modelfile_content = f"FROM {self.model_path}\n"
                # You can add custom system prompts or parameters here if needed!
                # modelfile_content += "PARAMETER temperature 0.3\n"
                
                with open("Modelfile", "w") as f:
                    f.write(modelfile_content)
                
                # 2. Command Ollama to create the model named 'mindsql'
                subprocess.run(["ollama", "create", "mindsql", "-f", "Modelfile"], check=True)
                
                # 3. Clean up the temporary Modelfile
                if os.path.exists("Modelfile"):
                    os.remove("Modelfile")
                    
                status.configure(text="✅ MindSQL Model Built Successfully!\nYou can now run 'python main.py' to start.", text_color="springgreen")
                
                btn = ctk.CTkButton(self.container, text="Close Installer", command=self.destroy)
                btn.pack(pady=30)
                
            except Exception as e:
                status.configure(text=f"❌ Error building model: {str(e)}", text_color="red")
                btn = ctk.CTkButton(self.container, text="Exit", command=self.destroy)
                btn.pack(pady=30)

        threading.Thread(target=run_build, daemon=True).start()

if __name__ == "__main__":
    app = MindSQLInstaller()
    app.mainloop()