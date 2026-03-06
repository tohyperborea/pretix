/*global eventreverse */
(function() {
    'use strict';
    
    function getOrdinalSuffix(num) {
        var j = num % 10;
        var k = num % 100;
        if (j === 1 && k !== 11) {
            return num + 'st';
        }
        if (j === 2 && k !== 12) {
            return num + 'nd';
        }
        if (j === 3 && k !== 13) {
            return num + 'rd';
        }
        return num + 'th';
    }
    
    function loadWaitingListRank() {
        var rankResult = document.getElementById('rank-result');
        
        if (!rankResult) {
            return;
        }
        
        var rankUrl = rankResult.getAttribute('data-rank-url');
        if (!rankUrl) {
            rankResult.textContent = 'Error: Rank URL not configured.';
            return;
        }
        
        fetch(rankUrl, {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.products !== undefined && !Array.isArray(data.products)) {
                data.products = [];
            }
            
            if (data.expired_voucher) {
                var expiredText = rankResult.getAttribute('data-expired-voucher-text') || 'You have an expired voucher.';
                var sentDateText = '';
                
                if (data.voucher_sent_date) {
                    try {
                        var sentDate = new Date(data.voucher_sent_date);
                        var dateOptions = { year: 'numeric', month: 'long', day: 'numeric' };
                        var formattedDate = sentDate.toLocaleDateString(undefined, dateOptions);
                        sentDateText = ' ' + (rankResult.getAttribute('data-sent-date-text') || 'It was sent on {date}.').replace('{date}', formattedDate);
                    } catch (e) {
                        // If date parsing fails, just show the expired message
                    }
                }
                
                rankResult.textContent = expiredText + sentDateText;
            } else if (data.rank !== undefined) {
                if (data.rank === 0) {
                    rankResult.textContent = rankResult.getAttribute('data-voucher-text') || 'You have a voucher waiting for redemption!';
                } else {
                    var rankLabel = rankResult.getAttribute('data-rank-label') || 'You are {ordinal} in line';
                    var ordinalRank = getOrdinalSuffix(data.rank);
                    rankResult.textContent = rankLabel.replace('{ordinal}', ordinalRank);
                }
            } else if (data.error) {
                rankResult.textContent = data.error;
            } else {
                rankResult.textContent = rankResult.getAttribute('data-error-text') || 'Unable to determine your rank.';
            }
        })
        .catch(function(error) {
            rankResult.textContent = rankResult.getAttribute('data-error-text') || 'An error occurred. Please try again.';
        });
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadWaitingListRank);
    } else {
        loadWaitingListRank();
    }
})();

