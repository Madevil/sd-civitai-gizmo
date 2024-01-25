import os
import gradio as gr
import json
import requests
from modules import hashes, script_callbacks, shared
from modules.paths_internal import models_path, data_path
import importlib

available_lora_hash_lookup = None
lora_base = None
lyco_base = None

def request_civit_api(api_url):
    try:
        _response = requests.get(api_url, timeout=(10, 30))
        _response.raise_for_status()
    except Exception as e:
        print(e)
        return str(e)
    else:
        _response.encoding = "utf-8"
        if _response.text.find("{") < 0:
            return _response.text
        return json.loads(_response.text)

def on_ui_tabs():

    _base_url = {
        "Hash": "https://civitai.com/api/v1/model-versions/by-hash/",
        "Version id": "https://civitai.com/api/v1/model-versions/",
    }

    with gr.Blocks() as _gr_block:

        with gr.Row(equal_height=False):
            _gr_tab_state = gr.State(["Hash"])
            with gr.Column(variant="panel"):
                with gr.Tabs():
                    with gr.Tab(label="Hash") as _gr_tab_hash:
                        with gr.Row():
                            _gr_tb_hash = gr.Textbox(label="Search Term:", info="supported hash algorithms: AutoV1, AutoV2, SHA256, CRC32, Blake3", interactive=True, lines=1)
                        with gr.Row():
                            _gr_btn_hash = gr.Button(value="Search")
                    with gr.Tab(label="Version id") as _gr_tab_ver:
                        with gr.Row():
                            _gr_tb_ver = gr.Textbox(label="Search Term:", info="number digits", interactive=True, lines=1)
                        with gr.Row():
                            _gr_btn_ver = gr.Button(value="Search")

                    _gr_tab_hash.select(lambda: ["Hash"], None, _gr_tab_state)
                    _gr_tab_ver.select(lambda: ["Version id"], None, _gr_tab_state)

                with gr.Row():
                    _gr_result = gr.HTML(value="")

            with gr.Column():
                with gr.Row():
                    _gr_debug_version = gr.Textbox(label="JSON (version):", show_label=True, interactive=False, lines=20)
                with gr.Row():
                    _gr_debug_model = gr.Textbox(label="JSON (model):", show_label=True, interactive=False, lines=20)

        def submit_click(sterm, stype):
            stype = stype[0]
            sterm = sterm.strip()
            _html = ""
            _version_json = ""
            _model_json = ""
            if sterm and stype in _base_url.keys():

                if stype == "Hash" and len(sterm) == 12 and len(available_lora_hash_lookup) > 0:
                    _found = None

                    for _key, _val in available_lora_hash_lookup.items():
                        if _key == sterm:
                            _found = _val #network.NetworkOnDisk
                            print(f"{_val.name} found via shorthash: {sterm}")
                            break

                    if _found:
                        _title = None
                        if _found.filename.startswith(lora_base):
                            _title = "lora/" + os.path.relpath(os.path.splitext(_found.filename)[0], lora_base).replace("/", "\\")
                        elif _found.filename.startswith(lyco_base):
                            _title = "locon/" + os.path.relpath(os.path.splitext(_found.filename)[0], lyco_base).replace("/", "\\")
                        else:
                            print(f"cannot determine lora type from filename: {_found.filename}")

                        if _title:
                            _sha256 = hashes.sha256(_found.filename, _title, False) #don't use addnet hash
                            if _sha256:
                                sterm = _sha256[:10]
                            else:
                                print(f"failed to get sha256 from {_found.filename}")

                _version_data = request_civit_api(_base_url[stype] + sterm)
                if type(_version_data) is dict and "id" in _version_data.keys() and "modelId" in _version_data.keys():
                    _version_json = json.dumps(_version_data, indent=4, ensure_ascii=False)
                    _model_id = _version_data["modelId"]
                    _version_id = _version_data["id"]
                    _model_data = request_civit_api(f"https://civitai.com/api/v1/models/{_model_id}")

                    if type(_model_data) is dict and "id" in _model_data.keys():
                        _html += f'{_model_data["name"]} ({_version_data["name"]})<br/><br/>'
                        _model_json = json.dumps(_model_data, indent=4, ensure_ascii=False)

                    _civitai_url = f'https://civitai.com/models/{_model_id}?modelVersionId={_version_id}'
                    _html += f'link: <a href="{_civitai_url}" target="_blank" id="ext_gizmo_result_link">{_civitai_url}</a><br/>'

                else:
                    _html = _version_data
            else:
                _html = "empty query submitted"

            return (
                gr.HTML.update(value=_html),
                gr.Textbox.update(value=_version_json),
                gr.Textbox.update(value=_model_json),
            )

        _gr_btn_hash.click(
            fn = submit_click,
            inputs = [
                _gr_tb_hash,
                _gr_tab_state
            ],
            outputs = [
                _gr_result,
                _gr_debug_version,
                _gr_debug_model,
            ]
        )

        _gr_btn_ver.click(
            fn = submit_click,
            inputs = [
                _gr_tb_ver,
                _gr_tab_state
            ],
            outputs = [
                _gr_result,
                _gr_debug_version,
                _gr_debug_model,
            ]
        )

    return (_gr_block, "Gizmo", "civitai_gizmo"),

script_callbacks.on_ui_tabs(on_ui_tabs)

def on_app_started(block, fastapi):

    global lora_base
    lora_base = get_lora_dir()

    global lyco_base
    lyco_base = get_locon_dir()

    global available_lora_hash_lookup
    if importlib.find_loader("lora") is not None:
        lora = importlib.import_module("lora")
        available_lora_hash_lookup = lora.available_lora_hash_lookup

script_callbacks.on_app_started(on_app_started)

def get_lora_dir():
    lora_dir = shared.opts.data.get('civitai_folder_lora', shared.cmd_opts.lora_dir).strip()
    if not lora_dir: lora_dir = shared.cmd_opts.lora_dir
    return lora_dir

def get_locon_dir():
    try:
        lyco_dir = shared.opts.data.get('civitai_folder_lyco', shared.cmd_opts.lyco_dir).strip()
        if not lyco_dir: lyco_dir = shared.cmd_opts.lyco_dir
        if not lyco_dir: lyco_dir = os.path.join(models_path, "LyCORIS"),
        return lyco_dir
    except:
        return get_lora_dir()
