Icon = Tea.Element.subclass({
    options: {
        cls: 'icon',
        type: '',
        status: 'active',
        colors: {
            "active":       "green",
            "struggling":   "green",
            "updating":     "gray",
            "deploying":    "gray",
            "redeploying":  "gray",
            "withdrawing":  "gray",
            "disabled":     "gray",
            "unknown":      "gray",
            "failed":       "red",
            "mia":          "red"
        }
    },
    setValue : function(status, type)
    {
        this._img = App.root + 'static/icons/' + type + '-' + this.options.colors[status] + '.png';
        if (this.source)
            this.source.css('background-image', "url(" + this._img + ")");
    },
    onRender : function()
    {
        if (this._img)
            this.source.css('background-image', this._img);
        else
            this.setValue(this.options.status, this.options.type);
    }
});

ServiceItem = Tea.Container.subclass({
    options: {
        cls: 'service item',
        value: null
    },
    onInit : function()
    {
        this.icon = new Icon();
        this.name = new Tea.Element({cls: 'name'});
        this.url =  new Tea.Element({cls: 'url'});
        this.info = new Tea.Element({cls: 'info'});
        
        this.append(this.icon);
        this.append(this.name);
        this.append(this.url);
        this.append(this.info);
    },
    onRender : function()
    {
        this.setValue(this.options.value);
    },
    setValue : function(v)
    {
        this.source.attr('class', 'service item ' + v.status + ' ' + v.type);
        
        this.icon.setValue(v.status, v.type);
        this.name.setHTML(v.name);
        this.url.setHTML(v.url);
        if (v.statusText)
            this.info.setHTML(v.status + " &ndash; " + v.statusText);
        else
            this.info.setHTML(v.status);
    },
    setFail : function(v)
    {
        this.source.attr('class', 'service item unknown');
        this.info.setHTML('unkown');
    }
});

LoadingElement = Tea.Element.subclass({
    options: {
        cls: 'loading item',
        value: null
    },
    onRender : function()
    {
        $('<div class="loading-icon icon"/>').appendTo(this.source);
        
        $('<div class="name">')
          .append("Loading")
          .appendTo(this.source);
    }
})

var App = new Tea.Application({
    stack: new Tea.StackContainer({ 
        skin: Tea.StackContainer.StretchySkin,
        column_width: 300
    }),
    
    ready : function()
    {
        this.stack.render().appendTo('#main');
        
        this.services = {};
        this.service_panel = new Tea.Panel({title: 'Services'});
        this.stack.push( this.service_panel );
        
        this.service_panel.append( this.loading = new LoadingElement() );
        
        this.load();
    },
    
    load : function()
    {
        $.ajax({
            url: App.root + 'services.json', 
            success: Tea.method(this.onLoad, this),
            dataType: "json",
        });
    },
    
    onLoad : function(services, status_code, request)
    {
        if (services == null)
        {
            this.timer = setTimeout(Tea.method(this.load, this), 3000);
            return this.onFail();
        }
        
        this.service_panel.remove( this.loading );
        
        var all = {};
        for(var i=0; i<services.length; i++)
        {
            this.setService(services[i]);
            all[services[i].path] = true;
        }
        
        for(var path in this.services)
        {
            if (!all[path])
            {
                this.services[path].remove();
                delete this.services[path];
            }
        }
        
        this.timer = setTimeout(Tea.method(this.load, this), 1000);
    },
    
    onFail : function()
    {
        for(var path in this.services)
        {
            this.services[path].setFail();
        }
    },
    
    setService : function(value)
    {
        if (this.services[value.path])
        {
            this.services[value.path].setValue(value);
        }
        else
        {
            var d = this.services[value.path] = new ServiceItem({
                value: value
            });
            this.service_panel.append(d);
        }
    }
})