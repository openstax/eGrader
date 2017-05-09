import $ from 'jquery'
import _ from 'underscore'

class API {
    constructor() {
        this.rootUrl = '/api/v1/'
    }

    getExercise(exerciseId) {
        const resource = 'exercises';
        let exercise = $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.rootUrl + resource + '/' + exerciseId
        });

        return exercise
    }
    
    getNextExercise(chapter_id) {
        const resource = 'exercise/next';
        let response = $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.rootUrl + resource,
            data: { chapter_id: chapter_id }
        });
        
        return response
    }

    getNextResponse(userId, exerciseId) {
        const resource = 'response/next';
        let response = $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.rootUrl + resource,
            data: { exercise_id: exerciseId }
        });

        return response
    }

    submitGradedResponse(data) {
        const resource = 'response/submit';
        var submit;
        // console.log(data);
        if (!(_.isEmpty(data))) {
            submit = $.ajax({
                url: this.rootUrl + resource,
                data: JSON.stringify(data),
                type: 'POST',
                contentType: "application/json; charset=utf-8"
            });
            // console.log(submit)

        } else {
            throw new Error('Data could not be submitted')
        }
        return submit
    }
    
    submitUnqualifiedExercise(data) {
        const resource = 'exercise/unqualified';
        let response = $.ajax({
            type: 'POST',
            dataType: 'json',
            url: this.rootUrl + resource,
            contentType: "application/json; charset=utf-8",
            data: JSON.stringify(data)
        });
        
        return response
        
    }

    submitNote(data) {
        const resource = 'exercise/notes';
        let response = $.ajax({
            type: 'POST',
            dataType: 'json',
            url: this.rootUrl + resource,
            contentType: "application/json; charset=utf-8",
            data: JSON.stringify(data)
        });

        return response
    }
    
    getNotes(userId, exerciseId) {
        const resource = 'exercise/notes';
        let response = $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.rootUrl + resource,
            data: {
                user_id: userId,
                exercise_id:exerciseId
            }
        });

        return response
    }
}

export default API
