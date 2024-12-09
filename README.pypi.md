<!-- <div align="center">
  <img src="https://github.com/arkohut/pensieve/raw/master/web/static/logos/memos_logo_512.png" width="250"/>
</div> -->

English | [简体中文](README_ZH.md) | [日本語](README_JP.md)

![pensieve-search](https://github.com/arkohut/pensieve/raw/master/docs/images/pensieve-search-en.gif)

[![哔哩哔哩](https://img.shields.io/badge/Bilibili-哔哩哔哩-%23fb7299)](https://www.bilibili.com/video/BV16XUkY7EJm) [![YouTube](https://img.shields.io/badge/YouTube-YouTube-%23ff0000)](https://www.youtube.com/watch?v=tAnYkeKTFUc)

> I changed the name to Pensieve because Memos was already taken.

# Pensieve (previously named Memos)

Pensieve is a privacy-focused passive recording project. It can automatically record screen content, build intelligent indices, and provide a convenient web interface to retrieve historical records.

This project draws heavily from two other projects: one called [Rewind](https://www.rewind.ai/) and another called [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c). However, unlike both of them, Pensieve allows you to have complete control over your data, avoiding the transfer of data to untrusted data centers.

## Features

- 🚀 Simple installation: just install dependencies via pip to get started
- 🔒 Complete data control: all data is stored locally, allowing for full local operation and self-managed data processing
- 🔍 Full-text and vector search support
- 🤖 Integrates with Ollama, using it as the machine learning engine for Pensieve
- 🌐 Compatible with any OpenAI API models (e.g., OpenAI, Azure OpenAI, vLLM, etc.)
- 💻 Supports Mac and Windows (Linux support is in development)
- 🔌 Extensible functionality through plugins

## Quick Start

![memos-installation](https://github.com/arkohut/pensieve/raw/master/docs/images/memos-installation.gif)

> [!IMPORTANT]  
> It seems that not all versions of Python's sqlite3 library support `enable_load_extension`. However, I'm not sure which environments or Python versions might encounter this issue. I use `conda` to manage Python, and Python installed via `conda` works fine on macOS, Windows x86, and Ubuntu 22.04.
>
> Please ensure the following command works in your Python environment:
>
> ```python
> import sqlite3
> 
> # Check sqlite version
> print(f"SQLite version: {sqlite3.sqlite_version}")
> 
> # Test if enable_load_extension is supported
> try:
>     conn = sqlite3.connect(':memory:')
>     conn.enable_load_extension(True)
>     print("enable_load_extension is supported")
> except AttributeError:
>     print("enable_load_extension is not supported")
> finally:
>     conn.close()
> ```
>
> If you find that this does not work properly, you can install [miniconda](https://docs.conda.io/en/latest/miniconda.html) to manage your Python environment. Alternatively, check the current issue list to see if others have encountered the same problem.

### 1. Install Pensieve

```sh
pip install memos
```

### 2. Initialize

Initialize the pensieve configuration file and sqlite database:

```sh
memos init
```

Data will be stored in the `~/.memos` directory.

### 3. Start the Service

```sh
memos enable
memos start
```

This command will:

- Begin recording all screens
- Start the Web service
- Set the service to start on boot

### 4. Access the Web Interface

Open your browser and visit `http://localhost:8839`

![init page](https://github.com/arkohut/pensieve/raw/master/docs/images/init-page-en.png)

### Mac Permission Issues

On Mac, Pensieve needs screen recording permission. When the program starts, Mac will prompt for screen recording permission - please allow it to proceed.

## User Guide

### Using the Appropriate Embedding Model

#### 1. Model Selection

Pensieve uses embedding models to extract semantic information and build vector indices. Therefore, choosing an appropriate embedding model is crucial. Depending on the user's primary language, different embedding models should be selected.

- For Chinese scenarios, you can use the [jinaai/jina-embeddings-v2-base-zh](https://huggingface.co/jinaai/jina-embeddings-v2-base-zh) model.
- For English scenarios, you can use the [jinaai/jina-embeddings-v2-base-en](https://huggingface.co/jinaai/jina-embeddings-v2-base-en) model.

#### 2. Adjust Memos Configuration

Open the `~/.memos/config.yaml` file with your preferred text editor and modify the `embedding` configuration:

```yaml
embedding:
  use_local: true
  model: jinaai/jina-embeddings-v2-base-en   # Model name used
  num_dim: 768                               # Model dimensions
  use_modelscope: false                      # Whether to use ModelScope's model
```

#### 3. Restart Memos Service

```sh
memos stop
memos start
```

The first time you use the embedding model, Pensieve will automatically download and load the model.

#### 4. Rebuild Index

If you switch the embedding model during use, meaning you have already indexed screenshots before, you need to rebuild the index:

```sh
memos reindex --force
```

The `--force` parameter indicates rebuilding the index table and deleting previously indexed screenshot data.

### Using Ollama for Visual Search

By default, Pensieve only enables the OCR plugin to extract text from screenshots and build indices. However, this method significantly limits search effectiveness for images without text.

To achieve more comprehensive visual search capabilities, we need a multimodal image understanding service compatible with the OpenAI API. Ollama perfectly fits this role.

#### Important Notes Before Use

Before deciding to enable the VLM feature, please note the following:

1. **Hardware Requirements**

   - Recommended configuration: NVIDIA graphics card with at least 8GB VRAM or Mac with M series chip
   - The minicpm-v model will occupy about 5.5GB of storage space
   - CPU mode is not recommended as it will cause severe system lag

2. **Performance and Power Consumption Impact**

   - Enabling VLM will significantly increase system power consumption
   - Consider using other devices to provide OpenAI API compatible model services

#### 1. Install Ollama

Visit the [Ollama official documentation](https://ollama.com) for detailed installation and configuration instructions.

#### 2. Prepare the Multimodal Model

Download and run the multimodal model `minicpm-v` using the following command:

```sh
ollama run minicpm-v "Describe what this service is"
```

This command will download and run the minicpm-v model. If the running speed is too slow, it is not recommended to use this feature.

#### 3. Configure Pensieve to Use Ollama

Open the `~/.memos/config.yaml` file with your preferred text editor and modify the `vlm` configuration:

```yaml
vlm:
  endpoint: http://localhost:11434  # Ollama service address
  modelname: minicpm-v              # Model name to use
  force_jpeg: true                  # Convert images to JPEG format to ensure compatibility
  prompt: Please describe the content of this image, including the layout and visual elements  # Prompt sent to the model
```

Use the above configuration to overwrite the `vlm` configuration in the `~/.memos/config.yaml` file.

Also, modify the `default_plugins` configuration in the `~/.memos/plugins/vlm/config.yaml` file:

```yaml
default_plugins:
- builtin_ocr
- builtin_vlm
```

This adds the `builtin_vlm` plugin to the default plugin list.

#### 4. Restart Pensieve Service

```sh
memos stop
memos start
```

After restarting the Pensieve service, wait a moment to see the data extracted by VLM in the latest screenshots on the Pensieve web interface:

![image](https://github.com/arkohut/pensieve/raw/master/./docs/images/single-screenshot-view-with-minicpm-result.png)

If you do not see the VLM results, you can:

- Use the command `memos ps` to check if the Pensieve process is running normally
- Check for error messages in `~/.memos/logs/memos.log`
- Confirm whether the Ollama model is loaded correctly (`ollama ps`)

### Full Indexing

Pensieve is a compute-intensive application. The indexing process requires the collaboration of OCR, VLM, and embedding models. To minimize the impact on the user's computer, Pensieve calculates the average processing time for each screenshot and adjusts the indexing frequency accordingly. Therefore, not all screenshots are indexed immediately by default.

If you want to index all screenshots, you can use the following command for full indexing:

```sh
memos scan
```

This command will scan and index all recorded screenshots. Note that depending on the number of screenshots and system configuration, this process may take some time and consume significant system resources. The index construction is idempotent, and running this command multiple times will not re-index already indexed data.

## Privacy and Security

During the development of Pensieve, I closely followed the progress of similar products, especially [Rewind](https://www.rewind.ai/) and [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c). I greatly appreciate their product philosophy, but they do not do enough in terms of privacy protection, which is a concern for many users (or potential users). Recording the screen of a personal computer may expose extremely sensitive private data, such as bank accounts, passwords, chat records, etc. Therefore, ensuring that data storage and processing are completely controlled by the user to prevent data leakage is particularly important.

The advantages of Pensieve are:

1. The code is completely open-source and easy-to-understand Python code, allowing anyone to review the code to ensure there are no backdoors.
2. Data is completely localized, all data is stored locally, and data processing is entirely controlled by the user. Data will be stored in the user's `~/.memos` directory.
3. Easy to uninstall. If you no longer use Pensieve, you can close the program with `memos stop && memos disable`, then uninstall it with `pip uninstall memos`, and finally delete the `~/.memos` directory to clean up all databases and screenshot data.
4. Data processing is entirely controlled by the user. Pensieve is an independent project, and the machine learning models used (including VLM and embedding models) are chosen by the user. Due to Pensieve' operating mode, using smaller models can also achieve good results.

Of course, there is still room for improvement in terms of privacy, and contributions are welcome to make Pensieve better.

## Other Noteworthy Content

### About Storage Space

Pensieve records the screen every 5 seconds and saves the original screenshots in the `~/.memos/screenshots` directory. Storage space usage mainly depends on the following factors:

1. **Screenshot Data**:

   - Single screenshot size: about 40-400KB (depending on screen resolution and display complexity)
   - Daily data volume: about 400MB (based on 10 hours of usage, single screen 2560x1440 resolution)
   - Multi-screen usage: data volume increases with the number of screens
   - Monthly estimate: about 8GB based on 20 working days

   Screenshots are deduplicated. If the content of consecutive screenshots does not change much, only one screenshot will be retained. The deduplication mechanism can significantly reduce storage usage in scenarios where content does not change frequently (such as reading, document editing, etc.).

2. **Database Space**:

   - SQLite database size depends on the number of indexed screenshots
   - Reference value: about 2.2GB of storage space after indexing 100,000 screenshots

### About Power Consumption

Pensieve requires two compute-intensive tasks by default:

- One is the OCR task, used to extract text from screenshots
- The other is the embedding task, used to extract semantic information and build vector indices

#### Resource Usage

- **OCR Task**: Executed using the CPU, and optimized to select the OCR engine based on different operating systems to minimize CPU usage
- **Embedding Task**: Intelligently selects the computing device

  - NVIDIA GPU devices prioritize using the GPU
  - Mac devices prioritize using Metal GPU
  - Other devices use the CPU

#### Performance Optimization Strategy

To avoid affecting users' daily use, Pensieve has adopted the following optimization measures:

- Dynamically adjust the indexing frequency, adapting to system processing speed
- Automatically reduce processing frequency when on battery power to save power

## Development Guide

### Peeling the First Layer of the Onion

In fact, after Pensieve starts, it runs three programs:

1. `memos serve` starts the web service
2. `memos record` starts the screenshot recording program
3. `memos watch` listens to the image events generated by `memos record` and dynamically submits indexing requests to the server based on actual processing speed

Therefore, if you are a developer or want to see the logs of the entire project running more clearly, you can use these three commands to run each part in the foreground instead of the `memos enable && memos start` command.
