import streamlit as st
import requests
import pandas as pd
from utils import format_search_results
import yaml
from io import StringIO

# --- Configuration ---
# Set the layout and title for the Streamlit page.
st.set_page_config(
    page_title="Data Lake Frontend",
    page_icon="🌊",
    layout="wide",
)

# ---------- FOLDER SEARCH HELPERS ----------


def _folder_search_params(
    project,
    author,
    experiment_type,
    tags_contain,
    date_after,
    date_before,
):
    params = {
        "project": project or None,
        "author": author or None,
        "experiment_type": experiment_type or None,
        "tags_contain": tags_contain or None,
        "date_after": date_after.isoformat() if date_after else None,
        "date_before": date_before.isoformat() if date_before else None,
    }
    return {k: v for k, v in params.items() if v is not None}


def _get_folder_results(api_base_url, params):
    r = requests.get(f"{api_base_url}/search", params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    # backend might return a list OR a dict with {"results":[...], "total":N}
    if isinstance(data, dict) and "results" in data:
        return data["results"], data.get("total", len(data))
    return data, len(data)


def _get_folder_files(api_base_url, folder_id):
    r = requests.get(f"{api_base_url}/folders/{folder_id}/files", timeout=60)
    r.raise_for_status()
    return r.json().get("files", [])


def _compute_subpath_options(files):
    """Return sorted unique directory prefixes ending with '/' derived from relative_path."""
    prefixes = set()
    for f in files:
        rp = (f.get("relative_path") or "").lstrip("/")
        if not rp or "/" not in rp:
            continue
        parts = rp.split("/")
        # build all intermediate directory prefixes (exclude the file itself)
        for i in range(1, len(parts)):  # up to parent
            prefixes.add("/".join(parts[:i]) + "/")
    return sorted(prefixes)


def show_upload_page(api_base_url):
    """Renders the upload page UI and logic."""
    st.header("Upload Data")

    # Create tabs for single file vs folder upload
    tab1, tab2 = st.tabs(["Upload Single File", "Upload Folder (as .zip)"])

    # --- Single File Upload Tab ---
    with tab1:
        st.markdown(
            "Select a single data file and fill in the metadata form to upload."
        )
        data_file = st.file_uploader(
            "Select Data File", type=None, key="single_file_uploader"
        )

        if data_file is not None:
            with st.form(key="single_file_metadata_form"):
                st.subheader(f"Metadata for: `{data_file.name}`")
                research_project_id = st.text_input(
                    "Research Project ID*",
                    placeholder="e.g., BBBO",
                    key="single_proj",
                )
                author = st.text_input(
                    "Author*", placeholder="e.g., wkm2109", key="single_author"
                )
                experiment_type = st.text_input(
                    "Experiment Type",
                    placeholder="e.g., Frequency_Sweep",
                    key="single_exp",
                )
                date_conducted = st.date_input("Date Conducted", key="single_date")
                custom_tags = st.text_input(
                    "Custom Tags (comma-separated)",
                    placeholder="e.g., tag1, important_data",
                    key="single_tags",
                )
                submit_button = st.form_submit_button(label="Upload File and Metadata")

                if submit_button:
                    if not research_project_id or not author:
                        st.error("Please fill in all required fields (*).")
                        return

                    metadata_dict = {
                        "research_project_id": research_project_id,
                        "author": author,
                        "experiment_type": experiment_type,
                        "date_conducted": date_conducted.isoformat()
                        if date_conducted
                        else None,
                        "custom_tags": custom_tags,
                    }
                    yaml_string = yaml.dump(metadata_dict, sort_keys=False)
                    metadata_file_obj = StringIO(yaml_string)
                    metadata_file_obj.name = "metadata.yaml"

                    files = {
                        "data_file": (data_file.name, data_file, data_file.type),
                        "metadata_file": (
                            metadata_file_obj.name,
                            metadata_file_obj.getvalue(),
                            "text/yaml",
                        ),
                    }

                    try:
                        with st.spinner(f"Uploading `{data_file.name}`..."):
                            response = requests.post(
                                f"{api_base_url}/uploadfile/", files=files, timeout=7200
                            )
                        if response.status_code == 200:
                            st.success("File processed successfully!")
                            st.json(response.json())
                        else:
                            st.error(
                                f"Upload failed. Status code: {response.status_code}"
                            )
                            try:
                                st.json(response.json())
                            except requests.exceptions.JSONDecodeError:
                                st.text(response.text)
                    except requests.exceptions.RequestException as e:
                        st.error(f"An error occurred during upload: {e}")

    # --- Folder (ZIP) Upload Tab ---
    with tab2:
        st.markdown(
            "Compress your folder into a `.zip` file, select it below, and fill in the metadata. The same metadata will be applied to **all files** within the folder."
        )

        zip_file = st.file_uploader(
            "Select .zip File", type=["zip"], key="zip_file_uploader"
        )

        if zip_file is not None:
            with st.form(key="folder_metadata_form"):
                st.subheader(f"Metadata for all files in: `{zip_file.name}`")
                research_project_id = st.text_input(
                    "Research Project ID*",
                    placeholder="e.g., BBBO",
                    key="folder_proj",
                )
                author = st.text_input(
                    "Author*", placeholder="e.g., wkm2109", key="folder_author"
                )
                experiment_type = st.text_input(
                    "Experiment Type",
                    placeholder="e.g., Frequency Sweep",
                    key="folder_exp",
                )
                date_conducted = st.date_input("Date Conducted", key="folder_date")
                custom_tags = st.text_input(
                    "Custom Tags (comma-separated)",
                    placeholder="e.g., tag1, important_data",
                    key="folder_tags",
                )
                submit_button = st.form_submit_button(
                    label="🚀 Upload Folder and Metadata"
                )

                if submit_button:
                    if not research_project_id or not author:
                        st.error("Please fill in all required fields (*).")
                        return

                    metadata_dict = {
                        "research_project_id": research_project_id,
                        "author": author,
                        "experiment_type": experiment_type,
                        "date_conducted": date_conducted.isoformat()
                        if date_conducted
                        else None,
                        "custom_tags": custom_tags,
                    }
                    yaml_string = yaml.dump(metadata_dict, sort_keys=False)
                    metadata_file_obj = StringIO(yaml_string)
                    metadata_file_obj.name = "metadata.yaml"

                    files = {
                        "zip_file": (zip_file.name, zip_file, "application/zip"),
                        "metadata_file": (
                            metadata_file_obj.name,
                            metadata_file_obj.getvalue(),
                            "text/yaml",
                        ),
                    }

                    try:
                        with st.spinner(
                            f"Uploading and processing `{zip_file.name}`... This may take a while."
                        ):
                            response = requests.post(
                                f"{api_base_url}/upload_folder/",
                                files=files,
                                timeout=7200,  # 2 hours for very large folders
                            )
                        if response.status_code == 200:
                            st.success("Folder processed successfully!")
                            st.json(response.json())
                        else:
                            st.error(
                                f"Upload failed. Status code: {response.status_code}"
                            )
                            try:
                                st.json(response.json())
                            except requests.exceptions.JSONDecodeError:
                                st.text(response.text)
                    except requests.exceptions.RequestException as e:
                        st.error(f"An error occurred during upload: {e}")


# --- UI Sections ---
def show_search_page(api_base_url):
    st.header("Search the Data Lake")
    tabs = st.tabs(["Folders", "Files"])

    # ---------- FOLDERS TAB ----------
    with tabs[0]:
        st.markdown(
            "Search folders by metadata. Select a folder to browse files and download the whole folder or a subfolder as a ZIP."
        )
        c1, c2 = st.columns(2)
        with c1:
            fld_project = st.text_input(
                "Project",
                placeholder="e.g., VectorY, Calibration ",
                key="folders_project",
            )
            fld_author = st.text_input(
                "Author", placeholder="e.g., wkm2109", key="folders_author"
            )
            fld_exp = st.text_input(
                "Experiment Type",
                placeholder="e.g., code, results, etc.",
                key="folders_exp",
            )
        with c2:
            fld_tags = st.text_input(
                "Tags Contain",
                placeholder="e.g., NHP, PCI, python, etc.",
                key="folders_tags",
            )
            d1, d2 = st.columns(2)
            with d1:
                fld_after = st.date_input(
                    "On or After", value=None, key="folders_after"
                )
            with d2:
                fld_before = st.date_input(
                    "On or Before", value=None, key="folders_before"
                )

        if st.button(
            "🔎 Search Folders", use_container_width=True, key="search_folders_btn"
        ):
            try:
                params = _folder_search_params(
                    fld_project,
                    fld_author,
                    fld_exp,
                    fld_tags,
                    fld_after,
                    fld_before,
                )
                with st.spinner("Searching folders..."):
                    folders, total = _get_folder_results(api_base_url, params)
                if not folders:
                    st.info("No folders found.")
                else:
                    st.success(f"Found {len(folders)} (total ~{total}).")
                    fdf = pd.DataFrame(folders)
                    # Keep common columns visible if present:
                    keep_cols = [
                        c
                        for c in [
                            "name",
                            "project",
                            "author",
                            "experiment_type",
                            "date_conducted",
                            "tags",
                            "id",
                            "created_at",
                        ]
                        if c in fdf.columns
                    ]
                    if keep_cols:
                        fdf = fdf[keep_cols]
                    st.dataframe(fdf, use_container_width=True, height=300)

                    # selection row
                    options = {
                        f"{row.get('name', '<unnamed>')}  •  {row.get('project', '')}  •  {row.get('id')}": row[
                            "id"
                        ]
                        for _, row in fdf.iterrows()
                    }
                    sel = st.selectbox(
                        "Select a folder to browse:",
                        list(options.keys()),
                        index=0,
                        key="folder_select_folder",
                    )
                    if sel:
                        folder_id = options[sel]

                        # Copyable folder id
                        st.caption("Folder ID (click to copy):")
                        st.code(folder_id)  # Streamlit shows a copy icon

                        # list files
                        with st.spinner("Loading files..."):
                            files = _get_folder_files(api_base_url, folder_id)

                        if files:
                            ff = pd.DataFrame(files)
                            show_cols = [
                                c
                                for c in [
                                    "relative_path",
                                    "size_bytes",
                                    "extension",
                                    "content_type",
                                    "file_id",
                                    "created_at",
                                ]
                                if c in ff.columns
                            ]
                            if show_cols:
                                ff = ff[show_cols]
                            st.dataframe(ff, use_container_width=True, height=350)

                            # download actions
                            st.markdown("### Download")
                            dcol1, dcol2 = st.columns(2)

                            with dcol1:
                                st.link_button(
                                    "📦 Download entire folder (ZIP)",
                                    url=f"{api_base_url}/folders/{folder_id}/download_zip",
                                    use_container_width=True,
                                )
                                st.markdown(
                                    f"[Click to download]({api_base_url}/folders/{folder_id}/download_zip)"
                                )

                            # subpath dropdown built from files
                            subpaths = _compute_subpath_options(files)
                            with dcol2:
                                sub_sel = st.selectbox(
                                    "Choose a subfolder to download (optional):",
                                    options=["(none)"] + subpaths,
                                    index=0,
                                    key="folder_subpath_select",
                                )
                                if sub_sel != "(none)":
                                    st.markdown(
                                        f"[Download subfolder]({api_base_url}/folders/{folder_id}/download_zip?subpath={sub_sel})"
                                    )
                        else:
                            st.info("This folder has no files.")

            except requests.exceptions.RequestException as e:
                st.error(f"Folder search failed: {e}")

    # ---------- FILES TAB (your existing UI moved here) ----------
    with tabs[1]:
        # your existing file search UI unchanged, or tweak labels:
        st.markdown(
            "Use the filters below to find files. Leave a field blank to ignore it."
        )
        col1, col2 = st.columns(2)
        with col1:
            research_project_id = st.text_input(
                "Research Project ID", placeholder="e.g., BBBO"
            )
            author = st.text_input("Author", placeholder="e.g., wkm2109")
            file_type = st.text_input("File Type", placeholder="e.g., PDF, MAT, TXT")
        with col2:
            experiment_type = st.text_input(
                "Experiment Type", placeholder="e.g., Data Calibration"
            )
            tags_contain = st.text_input(
                "Tags Contain", placeholder="e.g., 1.5V, 5hz, etc."
            )
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                date_after = st.date_input("Conducted On or After", value=None)
            with date_col2:
                date_before = st.date_input("Conducted On or Before", value=None)

        if st.button("🔎 Search Files", use_container_width=True):
            params = {
                "research_project_id": research_project_id or None,
                "author": author or None,
                "file_type": file_type or None,
                "experiment_type": experiment_type or None,
                "tags_contain": tags_contain or None,
                "date_after": date_after.isoformat() if date_after else None,
                "date_before": date_before.isoformat() if date_before else None,
            }
            params = {k: v for k, v in params.items() if v}
            try:
                with st.spinner("Searching..."):
                    response = requests.get(
                        f"{api_base_url}/search", params=params, timeout=60
                    )  # <-- if you kept /search_files, change path accordingly
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        st.success(f"Found {len(results)} matching files.")
                        st.session_state.search_results = results
                    else:
                        st.info("No files found.")
                        st.session_state.search_results = []
                else:
                    st.error(f"Search failed. Status code: {response.status_code}")
                    try:
                        st.json(response.json())
                    except:
                        st.text(response.text)
                    st.session_state.search_results = []
            except requests.exceptions.RequestException as e:
                st.error(f"An error occurred during search: {e}")
                st.session_state.search_results = []

        st.markdown("---")
        st.subheader("Results")
        if "search_results" in st.session_state and st.session_state.search_results:
            results_df = format_search_results(
                pd.DataFrame(st.session_state.search_results)
            )
            st.dataframe(results_df, use_container_width=True)
            st.markdown("---")
            st.subheader("Download a File:")
            filenames = results_df["file_name"].unique().tolist()
            selected_filename = st.selectbox(
                "Select a file to download:",
                options=filenames,
                index=None,
                placeholder="Choose a file...",
            )
            if selected_filename:
                matching_files = results_df[
                    results_df["file_name"] == selected_filename
                ]
                if len(matching_files) > 1:
                    st.warning(
                        f"Found {len(matching_files)} files named '{selected_filename}'. Select an exact File ID."
                    )
                    file_ids = matching_files["file_id"].tolist()
                    selected_file_id = st.selectbox(
                        "Select the exact File ID:",
                        options=file_ids,
                        index=None,
                        placeholder="Choose a File ID...",
                    )
                    if selected_file_id:
                        st.link_button(
                            f"Download File ID: {selected_file_id}",
                            url=f"{api_base_url}/download/{selected_file_id}",
                            use_container_width=True,
                        )
                else:
                    selected_file_id = matching_files.iloc[0]["file_id"]
                    st.link_button(
                        f"Download '{selected_filename}'",
                        url=f"{api_base_url}/download/{selected_file_id}",
                        use_container_width=True,
                    )
        else:
            st.write(
                "No search results to display. Use the filters above to start a new search."
            )


# --- Main App Logic ---

# --- Sidebar for Navigation and Settings ---
with st.sidebar:
    st.title("Navigation")
    page = st.radio(
        "Choose a page to navigate to:",
        ("Search/Download", "Upload"),
        label_visibility="collapsed",
    )

    st.markdown("---")

    with st.expander("Settings & API Status"):
        st.header("Settings")
        api_base_url = st.text_input(
            "Backend API URL",
            value="http://localhost:8001",
            help="The address of the FastAPI backend service.",
        )

        st.subheader("API Status")
        try:
            response = requests.get(f"{api_base_url}/status", timeout=5)
            if response.status_code == 200:
                st.success("Connected")
            else:
                st.error(f"Status: {response.status_code}")
        except requests.exceptions.RequestException:
            st.error("Connection Error")


# --- Page Content ---
if page == "Upload":
    show_upload_page(api_base_url)

elif page == "Search/Download":
    show_search_page(api_base_url)
