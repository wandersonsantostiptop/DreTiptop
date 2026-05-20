// DRE Tiptop – main.js

// Auto-dismiss flash messages after 5s
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(function () {
    document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(function (el) {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    });
  }, 5000);
});

// Format number inputs as BRL on blur (display only, not the actual value)
document.querySelectorAll('input[type="number"][step="0.01"]').forEach(function (input) {
  input.addEventListener('focus', function () {
    this.select();
  });
});
