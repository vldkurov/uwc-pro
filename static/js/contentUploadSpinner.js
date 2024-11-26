$(document).ready(function () {
    const spinnerBox = $("#spinner-box");
    const loadingText = $("#loading-text");
    const contentDraft = $("#content-draft");

    $("#content-form").on("submit", function () {
        spinnerBox.show();
        contentDraft.hide()
        loadingText.show();
    });

    $(window).on("load", function () {
        spinnerBox.hide();
        loadingText.hide();
        contentDraft.show()
    });
});