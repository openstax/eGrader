import $ from "jquery";
import _ from "underscore";
import noty from "noty";
import {activateFormWidget, activateNoteWidget, activateGraderSubmitButton} from "./events.js";
import API from "./api.js";
import getFormData from "./utils.js";
import {startMathJax, typesetMath} from "./mathjax.js";
import SocketManager from "./socket.js";
import Notes from "./notes.js";
import DropDown from "./dropdown.js";
//import LocalStorageManager from "./localstorage";

window.$ = window.jQuery = $;

var App = {

    start(userId) {
        startMathJax();
        this.userId = userId;

        // setup interfaces
        this.API = new API();
        this.socketManager = new SocketManager();
        // this.storageManager = new LocalStorageManager();

        this.activateEvents();

        this.getNextExercise();
    },

    activateEvents() {
        activateNoteWidget();
    },

    getNextExercise() {
        console.log('Getting new exercise');
        this.exerciseLoading();
        let self = this;
        let chapterId = this.chapterId;
        let exercise = this.API.getNextExercise(chapterId)
            .done(function(r) {
                let exerciseId = r['exercise_id'];
                self.exerciseId = exerciseId;
                console.log('Chapter Id is ' + self.chapterId);
                console.log('Exercise ' + exerciseId + ' is loading');
                self.loadExercise(exerciseId);
                self.notifyInformation('New Exercise Loaded!');
            })
            .fail(function(r) {
                throw new Error('There was a problem retrieving an exercise from the API')
            })
    },

    loadExercise(exerciseId) {
        let self = this;
        this.Notes = new Notes(self.userId, exerciseId);
        let exercise = this.API.getExercise(exerciseId)
            .done(function(r) {
                self.showExercise(r);
                self.nextResponse(self.userId, self.exerciseId);
                self.chapterId = r['chapter_id'];
                console.log('Chapter Id is ' + self.chapterId);
            })
            .fail(function(r) {
                // console.log(r);
                throw new Error('There was a problem retrieving an exercise from the API')
            });
    },

    showExercise(r) {
        let $eText = $('.exercise-text');
        let $eAnswer = $('.exercise-answer');
        let $uid = $('.exercise-identifier');
        
        $eText.empty();
        $eAnswer.empty();
        $uid.empty();
        
        console.log('loading exercise...');
        console.log(r);

        $eText.html(r['exercise_html']);
        $eAnswer.html(r['answer_html']);
        $uid.html('exercise id: ' + r['uid']);

        this.exerciseDelayLoad();

        this.feedbackChoices = r['feedback_choices'];

        this.Notes.loadNotes(this.userId, this.exerciseId);
        this.exerciseBookUrl = r['book_url'];

    },

    showResponse(r) {
        let $stuResponse = $('.stu-response');
        $stuResponse.html(r['response']['free_response']);
        console.log('loading response ' + r['response']['free_response']);

        // Need to set hidden field for response_id in the form
        this.loadGraderForm(this.feedbackChoices);
        $('#responseId').val(r['response']['id']);
    },

    nextResponse(userId, exerciseId) {
        let self = this;
        console.log("Getting next response");

        let response = this.API.getNextResponse(userId, exerciseId)
            .done(function(r) {
                if (r['success'] == true){
                    self.showResponse(r);
                } else {
                    self.getNextExercise();
                    console.log('No more responses for that exercise')
                }
            })
            .fail(function(r) {
                throw new Error('There was a problem retrieving a student response')
            })
    },

    loadFeedbackOptions(feedbackChoices) {
        // Grab feedback form element

        let $fChoices = $('.feedback-dropdown .choices');


        _.forEach(feedbackChoices, function(choice, index) {
            let $div= $('<div></div>').addClass('choice');

            $div.attr('data-value', choice[0]).html(choice[1]);
            $fChoices.append($div);

        });

        let dd = new DropDown($('.feedback-dropdown'), $('#feedbackId'));

        activateFormWidget();
        typesetMath(document);
        this.responseDelayLoad();

    },
    
    loadGraderForm(feedbackChoices) {
        let $container = $('.grader-form');
        let source = $('#grader-form-template').html();
        let template = _.template(source);
        $container.empty();
        $container.html(template());
        // record when the graderForm was loaded
        // technically the time when the grader would start grading
        this.startedOn = new Date();

        activateGraderSubmitButton(this.submitGraderResponse.bind(this));
        this.loadFeedbackOptions(feedbackChoices);
        console.log('Returned Feedback CHoices ' + feedbackChoices)
    },

    submitGraderResponse() {
        let self = this;
        let data = getFormData($('form'));

        const valid = this.validateForm(data);

        // inject the userId to the data as it's used by the
        // backend to save.. maybe better placed in a hidden form field?
        data['user_id'] = this.userId;
        data['session_id'] = this.socketManager.getSessionId();
        data['started_on'] = this.startedOn;
        console.log('adding started_on!' + this.responseLoaded);
        console.log('Trying to get sessionId' + this.socketManager.getSessionId());

        if (valid) {
            let submit = this.API.submitGradedResponse(data)
            .done(function(r) {
                // If successful we need to get the next response
                // If there are no more responses then get a new exercise
                console.log('Load the next response');
                self.nextResponse(self.userId, self.exerciseId);
                self.notifySuccess('Grade submitted!');
                self.responseLoading();
            })
            .fail(function(r) {
                throw new Error('There was a problem trying to save the graded response')
            });
        }

    },
    
    addNote() {
        let text = $('.notes-text').val();
        if (text) {
            console.log('Returned note text:' + text);
            this.Notes.addNote(this.userId, this.exerciseId, text)
        } else {
            this.notifyError('Please input a value into the text area.')
        }

    },

    submitUnqualifiedExercise() {
        let self = this;
        let data = {
            user_id: self.userId,
            exercise_id: self.exerciseId
        };
        this.exerciseLoading();
        this.responseLoading();

        let submit = this.API.submitUnqualifiedExercise(data)
            .done(function(r) {
                console.log('Submitted Qualification');
                self.getNextExercise();
                self.notifyInformation('Qualification Submitted!')
            })
            .fail(function(r) {
                throw new Error('There was a problem trying to save the qualification')
            })
    },
    
    notifySuccess(message) {
        new noty({
            text: message,
            layout: 'topRight',
            theme: 'relax',
            type: 'success',
            timeout: 3000
        })
    },
    
    notifyError(message) {
    new noty({
      text: message,
      layout: 'topRight',
      theme: 'relax',
      type: 'error',
      timeout: 3000 
    });
  },

    notifyInformation(message) {
        new noty({
            text: message,
            layout: 'topRight',
            theme: 'relax',
            type: 'information',
            timeout: 3000
        })
    },

    validateForm(data) {
        console.log(data);
        // map form elements other than qualtiy to a variable
        const score = data['score'] ? true:false;
        const misconception = data['misconception'] ? true:false;
        const feedback = data['feedback_id'] ? true:false;
        console.log(score, misconception, feedback);

        if (data['quality'] == 't') {
            // Return true immediately if junk = true
            return true
        } else if (data['quality'] == 'f') {
            //if junk = false then we need to validate the rest of the form
            if (score == false || misconception == false || feedback == false) {
                this.notifyError('There was an error. Please make sure you made all selections')
            } else {
                return true
            }
        } else {
            this.notifyError('There was an error. Please make a quality selection')
        }

    },
    
    showReferenceBook() {
        window.open(this.exerciseBookUrl);
    },

    exerciseLoading() {
        $('.exercise-container').addClass('loading');
        $('.exercise-text-area').hide();
    },

    exerciseLoaded() {
        $('.exercise-container').removeClass('loading');
        $('.exercise-text-area').show();
    },

    exerciseDelayLoad() {
        setTimeout(this.exerciseLoaded, 1000)

    },

    responseLoading() {
        $('.grader-form-container').addClass('loading');
        $('.grader-form').hide();
        $('.stu-response-container').hide();
    },

    responseLoaded() {
        $('.grader-form-container').removeClass('loading');
        $('.grader-form').show();
        $('.stu-response-container').show();
    },

    responseDelayLoad() {
        setTimeout(this.responseLoaded, 1000)
    }

};

window.App = App;
