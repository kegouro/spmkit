package main

import (
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
    "unsafe"
)

func message(s string) {
    text, _ := syscall.UTF16PtrFromString(s)
    title, _ := syscall.UTF16PtrFromString("Fathom · Apertura")
    syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW").Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
}

func main() {
    exe, err := os.Executable()
    if err != nil {message(err.Error());return}
    folder := filepath.Dir(exe)
    engine := filepath.Join(folder,"Motor")
    runner := filepath.Join(engine,"pythonw.exe")
    script := filepath.Join(engine,"iniciar.pyw")
    if _, err := os.Stat(script); err != nil {
        message("Extraiga todo el ZIP en una carpeta y abra este ejecutable desde allí. La carpeta Motor debe estar a su lado.")
        return
    }
    args := append([]string{"-B","-X","utf8",script},os.Args[1:]...)
    cmd := exec.Command(runner,args...)
    cmd.Dir = folder
    if err := cmd.Start(); err != nil {message("Fathom no pudo iniciar el motor.\n" + err.Error());return}
    cmd.Process.Release()
}
