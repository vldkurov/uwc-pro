$(document).ready(function () {

    function addForm(formsetId, formPrefix) {
        const $formset = $(`#${formsetId}`);
        const $totalForms = $(`#id_${formPrefix}-TOTAL_FORMS`);

        if (!$formset.length || !$totalForms.length) return;

        const formCount = parseInt($totalForms.val(), 10);

        const $templateForm = $formset.children(".form-row").last();
        const $newForm = $templateForm.length
            ? $templateForm.clone()
            : $("<div class='form-row d-flex align-items-center'></div>");

        $newForm.html(
            $newForm.html().replace(new RegExp(`${formPrefix}-(\\d+)-`, "g"), `${formPrefix}-${formCount}-`)
        );
        $newForm.find("input").val("");

        const $addButton = $formset.find(`#add-${formPrefix}`);
        if ($addButton.length) {
            $addButton.before($newForm);
        } else {
            $formset.append($newForm);
        }
        $totalForms.val(formCount + 1);
    }

    $("#add-phone").on("click", function () {
        addForm("phone-formset", "phones");
    });

    $("#add-email").on("click", function () {
        addForm("email-formset", "emails");
    });

    $("body").on("click", ".remove-phone, .remove-email", function () {
        const $formRow = $(this).closest(".form-row");
        const $deleteField = $formRow.find(`input[type="checkbox"][name$="-DELETE"]`);

        if ($deleteField.length) {
            $deleteField.prop("checked", true);
            $formRow.addClass("d-none");
        } else {
            $formRow.remove();
        }
    });
});