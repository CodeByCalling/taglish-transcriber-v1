07{ pkgs, ... }: {
  channel = "stable-23.11";
  packages = [
    pkgs.python3
    pkgs.ffmpeg
    pkgs.google-cloud-sdk
  ];
  env = {};
  idx = {
    extensions = [
      "ms-python.python"
    ];
    preview = {
      enable = true;
      previews = {
        web = {
          command = ["streamlit" "run" "app.py" "--server.port" "$PORT" "--server.enableCORS" "false" "--server.enableXsrfProtection" "false"];
          manager = "web";
        };
      };
    };
  };
}
