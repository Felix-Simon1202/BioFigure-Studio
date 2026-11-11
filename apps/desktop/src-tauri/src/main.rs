#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{io::{BufRead, BufReader, Write}, os::windows::{io::AsRawHandle, process::CommandExt},
    process::{Child, Command, Stdio}, sync::{mpsc, Mutex}, time::Duration};
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use windows_sys::Win32::{Foundation::{CloseHandle, GetLastError, HANDLE, ERROR_ALREADY_EXISTS},
    System::{JobObjects::*, Threading::CreateMutexW},
    UI::{WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK, MB_YESNO, MB_ICONQUESTION, IDYES}, Controls::Dialogs::*}};

fn wide(text: &str) -> Vec<u16> { text.encode_utf16().chain(Some(0)).collect() }
fn notice(text: &str) { unsafe { MessageBoxW(std::ptr::null_mut(), wide(text).as_ptr(), wide("BioFigure Studio").as_ptr(), MB_OK | MB_ICONERROR); } }

fn save_location(destination: &mut std::path::PathBuf, owner: windows_sys::Win32::Foundation::HWND) -> bool {
    let suggested = destination.file_name().and_then(|n| n.to_str()).unwrap_or("biofigure.png");
    let extension = destination.extension().and_then(|n| n.to_str()).unwrap_or("png");
    if !["svg", "pdf", "png"].contains(&extension) { return false; }
    let mut filename = vec![0u16; 32768];
    let name = wide(suggested);
    if name.len() >= filename.len() { return false; }
    filename[..name.len()].copy_from_slice(&name);
    let filter = wide(&format!("{} 图像\0*.{}\0\0", extension.to_uppercase(), extension));
    let default_extension = wide(extension);
    let mut dialog: OPENFILENAMEW = unsafe { std::mem::zeroed() };
    dialog.lStructSize = std::mem::size_of_val(&dialog) as u32;
    dialog.hwndOwner = owner;
    dialog.lpstrFile = filename.as_mut_ptr();
    dialog.nMaxFile = filename.len() as u32;
    dialog.lpstrFilter = filter.as_ptr();
    dialog.lpstrDefExt = default_extension.as_ptr();
    dialog.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    if unsafe { GetSaveFileNameW(&mut dialog) } == 0 { return false; }
    let end = filename.iter().position(|c| *c == 0).unwrap_or(filename.len());
    *destination = String::from_utf16_lossy(&filename[..end]).into();
    true
}

struct Engine { child: Mutex<Child>, job: HANDLE }
unsafe impl Send for Engine {}
unsafe impl Sync for Engine {}
impl Engine {
    fn stop(&self) {
        if let Ok(mut child) = self.child.lock() {
            child.stdin.take();
            for _ in 0..50 {
                if matches!(child.try_wait(), Ok(Some(_))) { return; }
                std::thread::sleep(Duration::from_millis(100));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
impl Drop for Engine { fn drop(&mut self) { self.stop(); unsafe { CloseHandle(self.job); } } }

fn launch(app: &tauri::App) -> Result<(Engine, tauri::Url), Box<dyn std::error::Error>> {
    let binary = app.path().resource_dir()?.join("engine/biofigure-engine.exe");
    let mut child = Command::new(binary).stdin(Stdio::piped()).stdout(Stdio::piped())
        .stderr(Stdio::null()).creation_flags(0x08000000).spawn()?;
    let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
    let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    let assigned = !job.is_null() && unsafe {
        SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits as *const _ as _, std::mem::size_of_val(&limits) as u32) != 0
        && AssignProcessToJobObject(job, child.as_raw_handle() as HANDLE) != 0
    };
    if !assigned {
        let _ = child.kill(); let _ = child.wait();
        if !job.is_null() { unsafe { CloseHandle(job); } }
        return Err("无法建立绘图进程退出保护".into());
    }
    let engine = Engine { child: Mutex::new(child), job };
    let output = {
        let mut child = engine.child.lock().unwrap();
        child.stdin.as_mut().unwrap().write_all(b"START\n")?;
        child.stdout.take().unwrap()
    };
    let (tx, rx) = mpsc::channel();
    std::thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(output).read_line(&mut line);
        let _ = tx.send(result.map(|_| line));
    });
    let line = rx.recv_timeout(Duration::from_secs(45))??;
    let data: serde_json::Value = serde_json::from_str(&line)?;
    let url: tauri::Url = data["url"].as_str().ok_or("引擎未返回本机地址")?.parse()?;
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") || url.port().is_none()
        || !url.path().starts_with("/_launch/") { return Err("引擎地址校验失败".into()); }
    Ok((engine, url))
}

fn main() {
    let mutex = unsafe { CreateMutexW(std::ptr::null(), 0, wide("Local\\BioFigureStudioDesktop").as_ptr()) };
    if mutex.is_null() { notice("无法建立启动锁，请重试。"); return; }
    if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
        notice("BioFigure Studio 已经运行，请使用已有窗口。");
        unsafe { CloseHandle(mutex); } return;
    }
    let result = tauri::Builder::default().setup(|app| {
        let (engine, url) = launch(app)?;
        let origin = url.origin();
        let download_origin = format!("blob:{}/", origin.ascii_serialization());
        app.manage(engine);
        WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
            .title("BioFigure Studio").inner_size(1280.0, 850.0).min_inner_size(760.0, 600.0)
            .incognito(true)
            .initialization_script("window.__BIOFIGURE_DESKTOP__ = true;")
            .on_navigation(move |next| next.origin() == origin)
            .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
            .on_download(move |webview, event| match event {
                tauri::webview::DownloadEvent::Requested { url, destination } => {
                    url.as_str().starts_with(&download_origin) && save_location(destination,
                        webview.window().hwnd().map(|h| h.0 as _).unwrap_or(std::ptr::null_mut()))
                }
                tauri::webview::DownloadEvent::Finished { success, .. } => {
                    if !success { notice("图像未保存成功，可能已取消或目标位置不可写。请重试。"); }
                    true
                }
                _ => false
            })
            .build()?;
        Ok(())
    }).on_window_event(|window, event| {
        if let tauri::WindowEvent::CloseRequested { api, .. } = event {
            let answer = unsafe { MessageBoxW(window.hwnd().map(|h| h.0 as _).unwrap_or(std::ptr::null_mut()),
                wide("退出后，本次导入的数据、配置与队列会话将结束。请先保存需要的图像。确定退出？").as_ptr(),
                wide("退出 BioFigure Studio").as_ptr(), MB_YESNO | MB_ICONQUESTION) };
            if answer != IDYES { api.prevent_close(); }
        }
    }).build(tauri::generate_context!());
    match result {
        Ok(app) => app.run(|handle, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                if let Some(engine) = handle.try_state::<Engine>() { engine.stop(); }
            }
        }),
        Err(_) => notice("桌面程序启动失败，请确认安装完整及 WebView2 可用。")
    }
    unsafe { CloseHandle(mutex); }
}
