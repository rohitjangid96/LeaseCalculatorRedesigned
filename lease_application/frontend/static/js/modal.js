function showAlert(message, type = 'info') {
    Swal.fire({
        text: message,
        icon: type,
        confirmButtonText: 'OK',
        customClass: {
            popup: 'custom-swal-popup',
            confirmButton: 'custom-swal-confirm-button'
        }
    });
}
