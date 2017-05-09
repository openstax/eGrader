class DropDown {
    constructor(el, hiddenField) {
        this.dd = el;
        this.choices = this.dd.children(':first');
        this.init();
        this.initEvents();
        this.count = 0;
        this.hiddenField = hiddenField;
    }

    init() {
        // Display the first option
        this.choices.children().addClass('inactive').hide();
        this.choices.children(':first').removeClass('inactive').addClass('active').show();
    }

    initEvents() {
        var obj = this;
        this.dd.on('click', '.choice', function(event) {
            if (obj.count == 0) {
                obj.count ++;
                obj.choices.children('.inactive').toggle();

                $(this).removeClass('active').addClass('inactive')

            } else {
                $(this).removeClass('inactive').addClass('active').show();

                obj.dd.css('height', $(this).height());
                obj.choices.children('.inactive').toggle();
                obj.count --;

                if (obj.hiddenField.length) {
                    obj.hiddenField.val($(this).attr('data-value'));
                }

            }

        });


    }

}

export default DropDown
