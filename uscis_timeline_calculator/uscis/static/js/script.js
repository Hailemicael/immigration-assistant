/**
 * USCIS Timeline Calculator
 * Main JavaScript file for form handling and dynamic content
 */

document.addEventListener('DOMContentLoaded', function() {
    // Form elements
    const formSelect = document.getElementById('form_number');
    const categorySelect = document.getElementById('form_category');
    const centerSelect = document.getElementById('service_center');
    const filingDateInput = document.getElementById('filing_date');
    const calculatorForm = document.getElementById('calculator-form');
    const errorContainer = document.getElementById('error-container');
    
    // Form categories by form type - these match the official USCIS categories
    const formCategories = {
        "I-130": ["Family-based: Immediate relative", "Family-based: F1", "Family-based: F2A", "Family-based: F2B", "Family-based: F3", "Family-based: F4"],
        "I-485": ["Family-based", "Employment-based", "Special Immigrant", "Asylee/Refugee", "VAWA"],
        "I-765": ["Initial EAD", "Renewal EAD", "Replacement EAD"],
        "I-90": ["Renewal/Replacement", "Biometric Update"],
        "N-400": ["Military", "Non-Military"],
        "I-129": ["H-1B", "L-1A", "L-1B", "O-1", "TN"],
        "I-140": ["EB-1", "EB-2", "EB-3", "National Interest Waiver"]
    };
    
    // Service centers
    const servicesCenters = [
        "California Service Center",
        "Nebraska Service Center",
        "Potomac Service Center",
        "Texas Service Center",
        "Vermont Service Center",
        "National Benefits Center",
        "Chicago Lockbox",
        "Dallas Lockbox",
        "Phoenix Lockbox"
    ];
    
    // Initialize form with today's date
    if (filingDateInput && !filingDateInput.value) {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        filingDateInput.value = `${year}-${month}-${day}`;
    }
    
    // Handle form type change
    if (formSelect) {
        formSelect.addEventListener('change', function() {
            const selectedForm = this.value;
            
            // Update categories
            if (categorySelect) {
                categorySelect.innerHTML = '<option value="" disabled selected>Select One</option>';
                
                if (formCategories[selectedForm]) {
                    formCategories[selectedForm].forEach(category => {
                        const option = document.createElement('option');
                        option.value = category;
                        option.textContent = category;
                        categorySelect.appendChild(option);
                    });
                    categorySelect.disabled = false;
                } else {
                    // If no categories available, add a default option
                    const defaultOption = document.createElement('option');
                    defaultOption.value = "Standard Processing";
                    defaultOption.textContent = "Standard Processing";
                    categorySelect.appendChild(defaultOption);
                    categorySelect.disabled = false;
                }
            }
            
            // Update service centers
            if (centerSelect) {
                centerSelect.innerHTML = '<option value="" disabled selected>Select One</option>';
                
                servicesCenters.forEach(center => {
                    const option = document.createElement('option');
                    option.value = center;
                    option.textContent = center;
                    centerSelect.appendChild(option);
                });
                centerSelect.disabled = false;
            }
        });
    }
    
    // Form validation
    if (calculatorForm) {
        calculatorForm.addEventListener('submit', function(e) {
            let hasErrors = false;
            let errorMessages = [];
            
            // Validate form type
            if (formSelect && !formSelect.value) {
                hasErrors = true;
                errorMessages.push('Please select a form type');
            }
            
            // Validate form category
            if (categorySelect && !categorySelect.value) {
                hasErrors = true;
                errorMessages.push('Please select a form category');
            }
            
            // Validate service center
            if (centerSelect && !centerSelect.value) {
                hasErrors = true;
                errorMessages.push('Please select a field office or service center');
            }
            
            // Validate filing date
            if (filingDateInput && !filingDateInput.value) {
                hasErrors = true;
                errorMessages.push('Please enter a filing date');
            }
            
            // Display errors if any
            if (hasErrors && errorContainer) {
                e.preventDefault();
                errorContainer.innerHTML = errorMessages.map(msg => `<div>${msg}</div>`).join('');
                errorContainer.style.display = 'block';
                errorContainer.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }
    
    // Print functionality in results page
    const printButton = document.getElementById('print-button');
    if (printButton) {
        printButton.addEventListener('click', function() {
            window.print();
        });
    }
    
    // Timeline chart error handling
    const timelineChart = document.getElementById('timeline-chart');
    if (timelineChart) {
        timelineChart.addEventListener('error', function() {
            // Show error message if image fails to load
            this.parentNode.innerHTML += '<div class="alert alert-warning mt-3"><i class="fas fa-exclamation-triangle me-2"></i> Chart could not be loaded. Please try refreshing the page.</div>';
        });
    }
});