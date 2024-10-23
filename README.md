<div align="center">
  <img src="web/static/logos/memos_logo_512.png" width="250"/>
</div>

English | [简体中文](README_ZH.md)

# Memos

Memos is a privacy-focused passive recording project. It can automatically record screen content, build intelligent indices, and provide a web interface to retrieve historical records.

This project draws heavily from two other projects: one called [Rewind](https://www.rewind.ai/) and another called [Windows Recall](https://support.microsoft.com/en-us/windows/retrace-your-steps-with-recall-aa03f8a0-a78b-4b3e-b0a1-2eb8ac48701c). However, unlike both of them, Memos allows you to have complete control over your data, avoiding the transfer of data to untrusted data centers.

## Quick Start

### 1. Install Memos

```sh
pip install memos
```

### 2. Initialize

Initialize the memos configuration file and sqlite database:

```sh
memos init
```

Data will be stored in the `~/.memos` directory.

### 3. Start the Service

```sh
memos start
```

This command will:

- Begin recording all screens
- Start the Web service

### 4. Access the Web Interface

Open your browser and visit `http://localhost:8839`

- Default username: `admin`
- Default password: `changeme`
