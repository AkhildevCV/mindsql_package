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
        self.geometry("600.450")
        self.resizable(False, False)
        
        self.os_type = platform.system()
        self.model_path = None
        # YOUR GITHUB REPO
        self.repo_url = "https://github.com/AkhildevCV/mindsql_package.git"

        # --- Main Container ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=40, pady=40)

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

        self.status_label = ctk.CTkLabel(self.container, text="Checking system requirements (Ollama & Git)...", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=20)

        self.action_btn = ctk.CTkButton(self.container, text="Start System Check", command=self.check_requirements, height=40)
        self.action_btn.pack(pady=20)

    def check_requirements(self):
        """Checks for both Ollama and Git."""
        ollama_installed = False
        git_installed = False

        # Check Ollama
        try:
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
            ollama_installed = True
        except: pass

        # Check Git
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            git_installed = True
        except: pass

        if ollama_installed and git_installed:
            self.status_label.configure(text="✅ All requirements met.", text_color="springgreen")
            self.action_btn.configure(text="Next Step", command=self.create_model_screen)
        elif not ollama_installed:
            self.status_label.configure(text="❌ Ollama not found.", text_color="red")
            self.action_btn.configure(text="Install Ollama Automatically", command=self.install_ollama)
        else:
            self.status_label.configure(text="❌ Git not found. Please install Git to continue.", text_color="red")
            self.action_btn.configure(text="Retry Check", command=self.check_requirements)

    def install_ollama(self):
        self.status_label.configure(text=f"Installing Ollama for {self.os_type}...", text_color="yellow")
        self.action_btn.configure(state="disabled")
        
        def run_install():
            try:
                if self.os_type == "Windows":
                    urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", "OllamaSetup.exe")
                    subprocess.run(["OllamaSetup.exe"], check=True)
                elif self.os_type == "Linux":
                    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
                
                self.status_label.configure(text="✅ Ollama Installed. Restarting check...", text_color="springgreen")
                self.action_btn.configure(state="normal", text="Check Again", command=self.check_requirements)
            except Exception as e:
                self.status_label.configure(text=f"❌ Install failed: {e}", text_color="red")
                self.action_btn.configure(state="normal", text="Retry", command=self.install_ollama)

        threading.Thread(target=run_install, daemon=True).start()

    # ==========================================
    # SCREEN 2: Model Configuration
    # ==========================================
    def create_model_screen(self):
        self.clear_container()
        title = ctk.CTkLabel(self.container, text="AI Model Setup", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=(0, 20))

        desc = ctk.CTkLabel(self.container, text="Link your local .gguf or download from Hugging Face.")
        desc.pack(pady=(0, 30))

        local_btn = ctk.CTkButton(self.container, text="Link Local .gguf File", command=self.link_local_model, height=40, fg_color="transparent", border_width=2)
        local_btn.pack(pady=10, fill="x")

        hf_btn = ctk.CTkButton(self.container, text="Download from Hugging Face", command=self.download_hf_model, height=40)
        hf_btn.pack(pady=10, fill="x")

        self.path_label = ctk.CTkLabel(self.container, text="", text_color="gray")
        self.path_label.pack(pady=20)

    def link_local_model(self):
        file_path = filedialog.askopenfilename(filetypes=[("GGUF Models", "*.gguf")])
        if file_path:
            self.model_path = file_path
            self.finish_installation()

    def download_hf_model(self):
        self.path_label.configure(text="Downloading model... please wait.", text_color="yellow")
        def run_download():
            # Placeholder for actual URL
            self.model_path = os.path.join(os.getcwd(), "mindsql-v2.gguf")
            # urllib.request.urlretrieve("YOUR_HF_URL", self.model_path)
            self.finish_installation()
        threading.Thread(target=run_download, daemon=True).start()

    # ==========================================
    # SCREEN 3: Final Setup (Code Clone + Model Build)
    # ==========================================
    def finish_installation(self):
        self.clear_container()
        title = ctk.CTkLabel(self.container, text="Finalize Installation", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=20)

        self.status_final = ctk.CTkLabel(self.container, text="Ready to clone repository and build model.", text_color="white")
        self.status_final.pack(pady=10)

        self.final_btn = ctk.CTkButton(self.container, text="Finish Setup", command=self.run_final_steps)
        self.final_btn.pack(pady=20)

    def run_final_steps(self):
        self.final_btn.configure(state="disabled")
        
        def run_task():
            try:
                # 1. CLONE THE REPOSITORY
                self.status_final.configure(text="📥 Cloning MindSQL repository...", text_color="cyan")
                if not os.path.exists(".git"): # Avoid error if already cloned
                    subprocess.run(["git", "clone", self.repo_url, "temp_repo"], check=True)
                    # Move files from temp_repo to current dir
                    import shutil
                    for item in os.listdir("temp_repo"):
                        s = os.path.join("temp_repo", item)
                        d = os.path.join(os.getcwd(), item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                    shutil.rmtree("temp_repo")

                # 2. CREATE OLLAMA MODEL
                self.status_final.configure(text="🧠 Building Ollama Model...", text_color="yellow")
                modelfile_content = f"FROM {self.model_path}\n"
                with open("Modelfile", "w") as f:
                    f.write(modelfile_content)
                
                subprocess.run(["ollama", "create", "mindsql", "-f", "Modelfile"], check=True)
                if os.path.exists("Modelfile"): os.remove("Modelfile")

                self.status_final.configure(text="✅ All Done! Run 'python main.py' to start.", text_color="springgreen")
                ctk.CTkButton(self.container, text="Close", command=self.destroy).pack(pady=10)
            except Exception as e:
                self.status_final.configure(text=f"❌ Error: {e}", text_color="red")
                self.final_btn.configure(state="normal")

        threading.Thread(target=run_task, daemon=True).start()

if __name__ == "__main__":
    app = MindSQLInstaller()
    app.mainloop()