function handleSubmit(tag) {
    const $tag = $(tag);
    const isButton = $tag.is('button');

    if (isButton) {

        const $button = $tag;
        const $hiddenInput = $('#hidden-amount');
        $hiddenInput.val($button.val());

        $('button[type="button"]').each(function () {
            const $loader = $(this).find('#loader');
            if ($loader.length) $loader.hide();
        });

        const $loader = $button.find('#loader');
        if ($loader.length) $loader.show();

        $button.closest('form').submit();
    } else {

        const $form = $tag;
        $form.find('button[type="submit"]').prop('disabled', true);

        const $loader = $form.find('#loader');
        if ($loader.length) $loader.show();
    }
}