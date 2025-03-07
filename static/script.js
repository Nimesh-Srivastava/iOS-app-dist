document.addEventListener('DOMContentLoaded', function() {
    // Add hover class for better touch devices
    const appCards = document.querySelectorAll('.app-card');
    
    appCards.forEach(card => {
        card.addEventListener('click', function(e) {
            if (!e.target.closest('.btn-install') && !e.target.closest('.btn-delete')) {
                this.classList.toggle('active');
            }
        });
    });

    // File input styling
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileName = this.files[0]?.name || 'No file chosen';
            const label = this.nextElementSibling;
            if (label) label.textContent = fileName;
        });
    });
});

const iconInput = document.getElementById('app-icon');
const imagePreview = document.createElement('img');
imagePreview.className = 'image-preview';
iconInput.parentNode.insertBefore(imagePreview, iconInput.nextSibling);

iconInput.addEventListener('change', function() {
    const file = this.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            imagePreview.src = e.target.result;
        }
        reader.readAsDataURL(file);
    }
});