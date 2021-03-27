

function setupTimestepTables(gather_url) {
    function persistTableData() {
        sessionStorage['timestep-data-'+gather_url] =JSON.stringify(window.dataTables);
    }

    function restoreTableData() {
        if(sessionStorage['timestep-data-'+gather_url] !== undefined)
        {
            try {
                window.dataTables = JSON.parse(sessionStorage['timestep-data-' + gather_url]);
            } catch(SyntaxError) {
                window.dataTables = {};
            }
        } else {
            window.dataTables = {}
        }
    }

    $(window).on('beforeunload',persistTableData);
    restoreTableData();
    window.gather_url = gather_url
}


function requestColumnData(editable_tag, miniLanguageQuery, callback) {
    if(window.dataTables === undefined ) {
        console.log("Attempt to request column data but the data tables have not yet been initialised")
        return undefined; // can't do anything useful
    }

    if(window.dataTables[editable_tag] === undefined) {
        window.dataTables[editable_tag] = {}
    }


    if(window.dataTables[editable_tag][miniLanguageQuery] === undefined) {
        var updateMarker = $("#update-marker-" + editable_tag);
        if(updateMarker!==undefined)
            updateMarker.html("<img src='/static/spinner.gif'>");
        let reqs = updateMarker.data("pending-requests")
        if (reqs === undefined) reqs = 0;
        updateMarker.data("pending-requests", reqs + 1)
        console.log("Requesting "+miniLanguageQuery+" for "+editable_tag+"...");
        $.ajax({
            type: "GET",
            url: gather_url + uriEncodeQuery(miniLanguageQuery) + ".json",
            success: function (data) {
                if(updateMarker!==undefined) {
                    let reqs = updateMarker.data("pending-requests")
                    if (reqs === 1)
                        $("#update-marker-" + editable_tag).html('');
                    updateMarker.data("pending-requests", reqs - 1)
                }
                window.dataTables[editable_tag][miniLanguageQuery] = data;
                if(callback!==undefined)
                   callback(window.dataTables[editable_tag][miniLanguageQuery]);
            }
        });
    } else {
        if(callback!==undefined)
            callback(window.dataTables[editable_tag][miniLanguageQuery]);
    }

}

function getFilterArray(object_tag, get_id_from='th', callbackAfterFetch = undefined) {
    let columnsToFilterOn = [];
    let dataToFilterOn = [];

    const re = /filter-(.*)/;
    $('#properties_form_'+object_tag+' input[type="checkbox"]').each(function() {
        let $this = $(this);
        if($this.prop('checked') && $this.is(":visible")) {
            let name = $this.attr('name').match(re)[1];
            columnsToFilterOn.push(uriDecodeQuery(name));
        }
    });


    $.each(columnsToFilterOn, function() {
       if(window.dataTables[object_tag][this]!==undefined) {
           dataToFilterOn.push(window.dataTables[object_tag][this].data_formatted);
       } else {
           if (callbackAfterFetch!==undefined) {
               requestColumnData(object_tag, this, callbackAfterFetch);
               return undefined;
           } // if no callback supplied, we carry on and get the best answer we can
       }
    });

    let nData = 0;

    try {
        nData = window.dataTables[object_tag]['halo_number()'].data_formatted.length;
    } catch(TypeError) {
        if (callbackAfterFetch!==undefined) {

           requestColumnData(object_tag, 'halo_number()', callbackAfterFetch);
       } // if no callback supplied, we carry on and get the best answer we can
        return undefined;
    }

    let filterArray = new Array(nData).fill(true);

    $.each(dataToFilterOn, function (j, c) {
        for(var i=0; i<nData; i++) {
            if (c[i] !== 'True') filterArray[i] = false;
        }
    });

    return filterArray;
}